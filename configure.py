"""Create ignored local settings and a version-pinned manifest without game input."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_patch
import runner

PATCH = Path(__file__).resolve().parent


def configure(install, adb_path=None, address=None):
    install = Path(install).resolve()
    settings_path = PATCH / "settings.json"
    config = runner.read_json(settings_path if settings_path.is_file() else PATCH / "settings.example.json")
    config["maa_install_root"] = str(install)
    if adb_path is not None:
        adb = Path(adb_path).resolve()
        if not adb.is_file():
            raise ValueError("adb.exe does not exist")
        config["adb_path"] = str(adb)
    if address is not None:
        config["address"] = address
    for start in runner.START_OPERATORS:
        params = runner.task_params(config, start)
        runner.validate_start_roles(params, runner.read_json(install / "resource/battle_data.json"))
    build_patch.build(install)
    settings_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Local settings prepared. No device was connected; no game task was started.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--adb-path", type=Path)
    parser.add_argument("--address")
    args = parser.parse_args()
    configure(args.install_root, args.adb_path, args.address)


if __name__ == "__main__":
    main()
