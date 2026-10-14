"""Isolated MAA API entry point. Offline by default; no desktop input APIs."""
from __future__ import annotations

import argparse
import ctypes
from dataclasses import dataclass, field
import datetime
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
PATCH = Path(__file__).resolve().parent
RUNTIME = PATCH / "runtime"
PREFIX = "BlackFlow@Roguelike@"
VICTORY = PREFIX + "N1ClearVictory"
FINAL_STAGES = {"永无安宁"}
PROFILE = "n1_clear"
STOP_FILE = RUNTIME / "stop.request"
START_OPERATORS = {"wisadel":"维什戴尔", "wang":"望", "mechanist":"机械师"}
START_ROLES = {"稳扎稳打":{"TANK","CASTER","SNIPER"},
               "先手必胜":{"PIONEER","SNIPER","SPECIAL"},
               "取长补短":{"WARRIOR","SUPPORT","MEDIC"},
               "灵活部署":{"PIONEER","SUPPORT","SPECIAL"},
               "坚不可摧":{"TANK","CASTER","MEDIC"}}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def installation_root(config, manifest):
    value = os.environ.get("MAA_INSTALL_ROOT") or config.get("maa_install_root") or manifest.get("install_root")
    if not value:
        raise ValueError("Configure your MAA installation with configure.py --install-root PATH first")
    return Path(value).resolve()


def check_integrity(install, manifest, *, include_config=False):
    table = manifest["base_hashes"] if include_config else manifest["required_hashes"]
    changed = [name for name, expected in table.items()
               if not (install/name).is_file() or sha256(install/name) != expected]
    if changed:
        raise ValueError("Original files differ from the version-pinned patch: " + ", ".join(changed))


def task_params(config, start=None):
    if not re.fullmatch(r"127\.0\.0\.1:([0-9]{1,5})",config.get("address","")):
        raise ValueError("This patch accepts only a local MuMu ADB address")
    if not 1 <= int(config["address"].rsplit(":",1)[-1]) <= 65535:
        raise ValueError("Invalid local ADB port")
    selected = start or config.get("default_start", "wisadel")
    if selected not in START_OPERATORS:
        raise ValueError("Unknown starting profile: " + str(selected))
    profiles = config.get("start_profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("start_profiles must be an object")
    profile = profiles.get(selected)
    # Keep the first release's settings usable for the original Wis'adel start.
    if profile is None and selected == "wisadel":
        profile = config
    if not isinstance(profile, dict):
        raise ValueError("Missing starting profile: " + selected)
    opers = profile.get("start_opers", [])
    if not isinstance(opers, list) or not 1 <= len(opers) <= 3:
        raise ValueError("start_opers must contain 1 to 3 operators")
    for oper in opers:
        if not isinstance(oper, dict) or not isinstance(oper.get("name"), str) or not oper["name"].strip():
            raise ValueError("Each starting operator needs a non-empty name")
        if not isinstance(oper.get("use_support", False), bool):
            raise ValueError("use_support must be a JSON boolean")
    if opers[0]["name"] != START_OPERATORS[selected]:
        raise ValueError("The first operator must match the selected starting profile")
    if any(o.get("use_support", False) for o in opers[1:]):
        raise ValueError("These profiles reserve the single support slot for the first operator")
    squad = profile.get("squad", config.get("squad"))
    roles = profile.get("roles", "稳扎稳打")
    if not isinstance(squad, str) or not squad:
        raise ValueError("A starting squad is required")
    if roles not in START_ROLES:
        raise ValueError("Choose a fixed starting ticket set")
    if selected == "mechanist" and squad in ("特勤分队", "堡垒战术分队"):
        raise ValueError("MaaCore mode 0 skips the other starting recruits for this Mechanist squad; use 指挥分队")
    return {"theme":"BlackFlow", "mode":0, "blackflow_strategy":PROFILE,
            "difficulty":1, "starts_count":1, "investment_enabled":False,
            "stop_at_final_boss":False, "stop_at_max_level":False,
            "squad":squad, "roles":roles,
            "core_char_list":[{"name":o["name"], "use_support":bool(o.get("use_support",False))} for o in opers],
            "use_nonfriend_support":bool(config.get("use_nonfriend_support",False)),
            "blackflow_diagnostics":"normal", "blackflow_diagnostic_image_limit":3}


def validate_start_roles(params, battle_data):
    professions = {}
    for char in battle_data["chars"].values():
        professions.setdefault(char["name"], set()).add(char["profession"])
    used = set()
    for oper in params["core_char_list"]:
        roles = professions.get(oper["name"], set())
        if len(roles) != 1:
            raise ValueError("Starting operator has an unknown or ambiguous profession: " + oper["name"])
        role = next(iter(roles))
        if role not in START_ROLES[params["roles"]] or role in used:
            raise ValueError("Starting professions must be distinct and available in " + params["roles"])
        used.add(role)


@dataclass
class RunMonitor:
    expected_support_name: str = ""
    support_confirmation_seen: bool = False
    profile_seen: bool = False
    difficulty_verified: bool = False
    current_stage: str = ""
    stage_started_at: float | None = None
    final_battle_finished: bool = False
    completed: bool = False
    failure: str = ""
    stages_seen: list[str] = field(default_factory=list)

    def observe(self, message, details, now=None):
        now = time.monotonic() if now is None else now
        if not isinstance(details, dict):
            self.fail("Malformed native callback")
            return
        nested = details.get("details", {})
        if not isinstance(nested, dict):
            nested = {}
        # AbstractTask::callback strips everything through the last '@'.
        task = str(nested.get("task", "")).rsplit("@",1)[-1]
        what = details.get("what", "")
        if message == 20003 and what == "BlackFlowStrategyStarted":
            if nested.get("profile") != PROFILE:
                self.fail("Native core did not select n1_clear")
            else:
                self.profile_seen = True
        if message == 20002 and task == "N1DifficultyVerified":
            self.difficulty_verified = True
        if message == 20002 and task == "RecruitSupportConfirm":
            self.support_confirmation_seen = True
        if message == 20001 and task == "EnterAfterRecruit" and self.expected_support_name and not self.support_confirmation_seen:
            self.fail("Required starting support was not confirmed: " + self.expected_support_name)
        if message == 20001 and task == "N1DifficultyCheckFailed":
            self.fail("Could not verify difficulty 1; no run was authorized")
        if message == 20003 and what == "StageInfo":
            self.current_stage = nested.get("name", "")
            self.stage_started_at = now
            self.stages_seen.append(self.current_stage)
            if not self.profile_seen or not self.difficulty_verified:
                self.fail("Battle started without the verified N1 profile")
            if self.expected_support_name and not self.support_confirmation_seen:
                self.fail("Battle started without the required starting support confirmation")
        if message == 20003 and what == "RoguelikeCombatEnd":
            # Native CombatEnd fires for defeats too; it alone is never a victory.
            if self.current_stage in FINAL_STAGES:
                self.final_battle_finished = True
            self.stage_started_at = None
        if message == 20002 and task == "N1ClearVictory":
            if self.profile_seen and self.difficulty_verified and self.final_battle_finished and not self.failure:
                self.completed = True
            else:
                self.fail("Victory page appeared without this run's N1 final battle evidence")
        if message == 20001 and task in ("MissionFailedFlag","MissionFailedFlag2","N1RunFailed","N1RunFailed2"):
            self.fail("Run failed; no automatic abandon or restart")
        if message == 20003 and what in ("StageInfoError", "BlackFlowStrategyResult"):
            self.fail("Stage recognition/route stopped: " + json.dumps(nested, ensure_ascii=False))
        forbidden = ("ExitThenAbandon", "AbandonConfirm", "ReturnConfirm", "ClickToStartPoint", "StartUpThemes")
        if message == 20001 and any(s in task for s in forbidden):
            self.fail("Blocked exit/restart task: " + task)
        if message in (0, 1, 10000) and not self.completed:
            self.fail("Native error: " + json.dumps(details, ensure_ascii=False))

    def fail(self, reason):
        if not self.failure:
            self.failure = reason


class ProcessLock:
    def __init__(self, name="Local\\MAA_BlackFlow_N1_Patch"):
        self.handle = None
        self.name = name
        from ctypes import wintypes
        self.kernel = ctypes.WinDLL("kernel32",use_last_error=True)
        self.kernel.CreateMutexW.argtypes = (ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR)
        self.kernel.CreateMutexW.restype = wintypes.HANDLE
        self.kernel.ReleaseMutex.argtypes = (wintypes.HANDLE,)
        self.kernel.CloseHandle.argtypes = (wintypes.HANDLE,)

    def __enter__(self):
        ctypes.set_last_error(0)
        self.handle = self.kernel.CreateMutexW(None,True,self.name)
        if not self.handle:
            raise OSError(ctypes.get_last_error(),"Cannot create patch mutex")
        if ctypes.get_last_error() == 183:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
            raise RuntimeError("Another N1 patch runner is already active, possibly from another folder")
        return self

    def __exit__(self, *args):
        if self.handle:
            self.kernel.ReleaseMutex(self.handle)
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def game_foreground(config):
    result = subprocess.run([config["adb_path"],"-s",config["address"],"shell","dumpsys","activity","activities"],
                            capture_output=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError("Cannot verify the Android foreground app")
    text = result.stdout.decode("utf-8",errors="replace")
    return bool(re.search(r"(?:topResumedActivity|mResumedActivity|ResumedActivity).*com\.hypergryph\.arknights(?:\.bilibili)?/",text))


def maa_gui_running():
    from ctypes import wintypes
    class Entry(ctypes.Structure):
        _fields_ = [("dwSize",wintypes.DWORD),("cntUsage",wintypes.DWORD),
                    ("th32ProcessID",wintypes.DWORD),("th32DefaultHeapID",ctypes.c_size_t),
                    ("th32ModuleID",wintypes.DWORD),("cntThreads",wintypes.DWORD),
                    ("th32ParentProcessID",wintypes.DWORD),("pcPriClassBase",wintypes.LONG),
                    ("dwFlags",wintypes.DWORD),("szExeFile",wintypes.WCHAR*260)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD,wintypes.DWORD)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = (wintypes.HANDLE,ctypes.POINTER(Entry))
    kernel.Process32NextW.argtypes = (wintypes.HANDLE,ctypes.POINTER(Entry))
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.CreateToolhelp32Snapshot(2,0)
    if handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), "Cannot inspect running MAA GUI")
    try:
        entry = Entry()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel.Process32FirstW(handle,ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == "maa.exe":
                return True
            ok = kernel.Process32NextW(handle,ctypes.byref(entry))
        return False
    finally:
        kernel.CloseHandle(handle)


def load_core(install, events):
    sys.path.insert(0, str(install/"Python"))
    from asst.asst import Asst
    @Asst.CallBackType
    def callback(message, raw, context):
        try:
            details = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception as exc:
            details = {"callback_decode_error":str(exc)}
            message = 0
        events.put((message,details))
    os.chdir(RUNTIME)
    if not Asst.load(install,incremental_path=PATCH,user_dir=RUNTIME):
        raise RuntimeError("Installed MaaCore rejected the resource overlay; inspect runtime/debug/asst.log")
    return Asst(callback=callback), callback


def drain(events, monitor, output=None):
    while True:
        try:
            message, details = events.get_nowait()
        except queue.Empty:
            return
        if output:
            output.write(json.dumps({"at":datetime.datetime.now().isoformat(),
                                     "message":message,"details":details},ensure_ascii=False)+"\n")
            output.flush()
        monitor.observe(message,details)
        if details.get("what") == "StageInfo":
            print("Stage:",monitor.current_stage,flush=True)


def save_result(path, result):
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline-check",action="store_true")
    mode.add_argument("--run",action="store_true")
    parser.add_argument("--config",type=Path,default=PATCH/"settings.json")
    parser.add_argument("--start",choices=tuple(START_OPERATORS),default=None)
    args = parser.parse_args()
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RuntimeError("This installed MAA requires 64-bit Windows Python")
    manifest_path = PATCH/"manifest.json"
    manifest = read_json(manifest_path if manifest_path.is_file() else PATCH/"compatibility.json")
    if not args.config.is_file():
        raise ValueError("Local settings.json is missing. Run configure.py first")
    config = read_json(args.config)
    install = installation_root(config, manifest)
    selected_start = args.start or config.get("default_start", "wisadel")
    params = task_params(config, selected_start)
    check_integrity(install,manifest)
    validate_start_roles(params, read_json(install/"resource/battle_data.json"))
    if args.run and maa_gui_running():
        raise RuntimeError("MAA.exe is open. Close the original GUI before running this API entry; the game stays open.")
    if args.run and not Path(config["adb_path"]).is_file():
        raise RuntimeError("Configured MuMu adb.exe not found; edit settings.json")
    timeout = int(config.get("battle_timeout_seconds",420))
    if not 30 <= timeout < 480:
        raise ValueError("battle_timeout_seconds must be 30..479 (before native 8-minute retreat)")
    RUNTIME.mkdir(exist_ok=True)
    with ProcessLock():
        events = queue.Queue()
        first_oper = params["core_char_list"][0]
        monitor = RunMonitor(expected_support_name=first_oper["name"] if first_oper["use_support"] else "")
        asst, callback = load_core(install,events)
        version = asst.get_version()
        print("MaaCore:",version,flush=True)
        print("Start:",first_oper["name"],"(support)" if first_oper["use_support"] else "(own)",flush=True)
        if not asst.append_task("Roguelike",params):
            raise RuntimeError("Installed MaaCore rejected Roguelike task parameters")
        for _ in range(20):
            drain(events,monitor)
            if monitor.profile_seen or monitor.failure:
                break
            time.sleep(0.05)
        if not monitor.profile_seen or monitor.failure:
            raise RuntimeError(monitor.failure or "Native core did not initialize n1_clear")
        if not args.run:
            result = {"offline_check":True,"resource_load":True,"native_task_accepted":True,
                      "profile_initialized":monitor.profile_seen,"version":version,
                      "device_connected":False,"task_started":False,"combat_tested":False,
                      "stage_count":manifest["stage_count"],"start_profile":selected_start,
                      "core_char_list":params["core_char_list"],"squad":params["squad"],"roles":params["roles"]}
            check_integrity(install,manifest)
            save_result(RUNTIME/"offline-check.json",result)
            save_result(RUNTIME/("offline-check-"+selected_start+".json"),result)
            print("PASS: overlay and N1 profile loaded. No device connection or game input.")
            return 0
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        result_path = RUNTIME/("result-"+stamp+".json")
        if STOP_FILE.exists():
            raise RuntimeError("A stop.request is present. Clear it after checking the game before starting a new run.")
        session_start = time.monotonic()
        limit_minutes = int(config.get("max_run_minutes",180))
        if not 5 <= limit_minutes <= 360:
            raise ValueError("max_run_minutes must be 5..360")
        try:
            from asst.utils import InstanceOptionType
            if not asst.set_instance_option(InstanceOptionType.touch_type,"maatouch"):
                raise RuntimeError("Cannot select Android-only MaaTouch input")
            if not asst.set_instance_option(InstanceOptionType.kill_on_adb_exit,"0"):
                raise RuntimeError("Cannot disable ADB-server termination")
            if not asst.connect(config["adb_path"],config["address"],"General"):
                raise RuntimeError("Cannot connect to MuMu. No emulator restart or ADB-server kill attempted.")
            if not game_foreground(config):
                raise RuntimeError("Arknights is not the Android foreground app; task not started")
            if not asst.start():
                raise RuntimeError("MAA task did not start")
            print("Single N1 run started via MuMu ADB; Ctrl+C stops input.",flush=True)
            last_app_check = time.monotonic()
            with (RUNTIME/("events-"+stamp+".jsonl")).open("w",encoding="utf-8") as output:
                while True:
                    drain(events,monitor,output)
                    now = time.monotonic()
                    if now-last_app_check > 5:
                        if not game_foreground(config):
                            monitor.fail("Android foreground app changed; stopping input")
                        last_app_check = now
                    if STOP_FILE.exists():
                        monitor.fail("Stopped by stop.request")
                    if now-session_start > limit_minutes*60:
                        monitor.fail("Run time limit reached")
                    if monitor.stage_started_at is not None and now-monitor.stage_started_at > timeout:
                        monitor.fail("Battle time limit reached; stopping before native retreat/abandon")
                    if monitor.completed or monitor.failure:
                        break
                    if not asst.running():
                        time.sleep(0.1)
                        drain(events,monitor,output)
                        if not monitor.completed:
                            monitor.fail("Task stopped without verified N1 victory")
                        break
                    time.sleep(0.1)
        except KeyboardInterrupt:
            monitor.fail("Stopped by user")
        except Exception as exc:
            monitor.fail(str(exc))
        finally:
            # Never call stop() from the native callback: that can deadlock the worker.
            asst.stop()
            drain(events,monitor)
            result = {"completed":monitor.completed,"difficulty":1,"profile":PROFILE,
                      "start_profile":selected_start,"core_char_list":params["core_char_list"],
                      "support_confirmation_seen":monitor.support_confirmation_seen,
                      "failure":monitor.failure,"difficulty_verified":monitor.difficulty_verified,
                      "final_battle_finished":monitor.final_battle_finished,
                      "stages_seen":monitor.stages_seen,"version":version,
                      "elapsed_seconds":round(time.monotonic()-session_start,1)}
            save_result(result_path,result)
        print("VERIFIED N1 VICTORY" if monitor.completed else "STOPPED: "+monitor.failure,flush=True)
        print("Result:",result_path,flush=True)
        return 0 if monitor.completed else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("ERROR:",exc,file=sys.stderr,flush=True)
        sys.exit(1)
