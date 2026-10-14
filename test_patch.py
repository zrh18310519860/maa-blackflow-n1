import copy
import json
import os
from pathlib import Path
import unittest
from unittest import mock

import build_patch
import runner

PATCH = Path(__file__).resolve().parent


def load(path):
    if path == PATCH/"settings.json" and not path.is_file():
        path = PATCH/"settings.example.json"
    return json.loads(path.read_text(encoding="utf-8-sig"))


def event(monitor, message, *, task="", what="", **details):
    if task:
        details["task"] = task.rsplit("@",1)[-1]
    monitor.observe(message,{"what":what,"details":details},now=100.0)


class MonitorTests(unittest.TestCase):
    def prepared(self):
        monitor = runner.RunMonitor()
        event(monitor,20003,what="BlackFlowStrategyStarted",profile="n1_clear")
        event(monitor,20002,task=runner.PREFIX+"N1DifficultyVerified")
        return monitor

    def test_native_combat_end_is_not_victory(self):
        m = self.prepared()
        event(m,20003,what="StageInfo",name="永无安宁")
        event(m,20003,what="RoguelikeCombatEnd")
        self.assertFalse(m.completed)

    def test_verified_final_page_is_required(self):
        m = self.prepared()
        event(m,20003,what="StageInfo",name="永无安宁")
        event(m,20003,what="RoguelikeCombatEnd")
        event(m,20002,task=runner.VICTORY)
        self.assertTrue(m.completed)
        self.assertFalse(m.failure)

    def test_final_page_from_old_run_is_not_victory(self):
        m = self.prepared()
        event(m,20002,task=runner.VICTORY)
        self.assertFalse(m.completed)
        self.assertTrue(m.failure)

    def test_final_page_without_difficulty_is_not_victory(self):
        m = runner.RunMonitor(profile_seen=True)
        event(m,20003,what="StageInfo",name="永无安宁")
        event(m,20003,what="RoguelikeCombatEnd")
        event(m,20002,task=runner.VICTORY)
        self.assertFalse(m.completed)

    def test_third_floor_boss_is_not_victory(self):
        m = self.prepared()
        event(m,20003,what="StageInfo",name="光荣远征")
        event(m,20003,what="RoguelikeCombatEnd")
        event(m,20002,task=runner.VICTORY)
        self.assertFalse(m.completed)

    def test_defeat_cannot_be_reclassified(self):
        m = self.prepared()
        event(m,20003,what="StageInfo",name="永无安宁")
        event(m,20003,what="RoguelikeCombatEnd")
        event(m,20001,task=runner.PREFIX+"MissionFailedFlag")
        event(m,20002,task=runner.VICTORY)
        self.assertFalse(m.completed)

    def test_wrong_profile_blocks_battle(self):
        m = runner.RunMonitor()
        event(m,20003,what="BlackFlowStrategyStarted",profile="burn")
        self.assertTrue(m.failure)
        self.assertFalse(m.profile_seen)

    def test_route_success_is_not_game_success(self):
        m = self.prepared()
        event(m,20003,what="BlackFlowStrategyResult",succeeded=True)
        self.assertFalse(m.completed)
        self.assertTrue(m.failure)

    def test_exit_is_blocked(self):
        m = self.prepared()
        event(m,20001,task=runner.PREFIX+"ReturnConfirm")
        self.assertTrue(m.failure)

    def test_core_normal_finish_does_not_invent_victory(self):
        m = self.prepared()
        event(m,10002)
        self.assertFalse(m.completed)

    def test_recognition_failure(self):
        m = self.prepared()
        event(m,20003,what="StageInfoError")
        self.assertTrue(m.failure)

    def test_fully_qualified_callbacks_also_work(self):
        m = self.prepared()
        m.observe(20002,{"details":{"task":runner.PREFIX+"N1DifficultyVerified"}})
        self.assertTrue(m.difficulty_verified)

    @unittest.skipUnless(os.name == "nt", "Windows named mutex")
    def test_mutex_prevents_two_copies_controlling_one_device(self):
        name = f"Local\\MAA_BlackFlow_N1_Test_{os.getpid()}"
        with runner.ProcessLock(name):
            with self.assertRaises(RuntimeError):
                with runner.ProcessLock(name):
                    self.fail("Second lock must fail")
        with runner.ProcessLock(name):
            pass

    def test_borrowed_start_requires_support_confirmation(self):
        m = self.prepared()
        m.expected_support_name = "望"
        event(m,20001,task=runner.PREFIX+"EnterAfterRecruit")
        self.assertIn("望",m.failure)
        self.assertFalse(m.support_confirmation_seen)

    def test_support_confirmation_allows_start(self):
        m = self.prepared()
        m.expected_support_name = "机械师"
        event(m,20002,task=runner.PREFIX+"RecruitSupportConfirm")
        event(m,20001,task=runner.PREFIX+"EnterAfterRecruit")
        event(m,20003,what="StageInfo",name="猎犬病原")
        self.assertTrue(m.support_confirmation_seen)
        self.assertFalse(m.failure)

    def test_battle_also_blocks_missing_support_confirmation(self):
        m = self.prepared()
        m.expected_support_name = "望"
        event(m,20003,what="StageInfo",name="猎犬病原")
        self.assertTrue(m.failure)


class ResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load(PATCH/"compatibility.json")
        config = load(PATCH/"settings.json")
        root = os.environ.get("MAA_INSTALL_ROOT") or config.get("maa_install_root")
        cls.install = Path(root) if root else PATCH/"base-snapshot"
        cls.r = PATCH/"resource/roguelike/BlackFlow"

    def test_all_json_parses(self):
        for path in PATCH.rglob("*.json"):
            if "base-snapshot" in path.parts:
                continue
            with self.subTest(path=path):
                load(path)

    def test_original_files_unchanged(self):
        if not (self.install/"MaaCore.dll").is_file():
            self.skipTest("Native installation not configured; using public resource fixtures")
        runner.check_integrity(self.install,self.manifest)
        for name,expected in self.manifest.get("build_input_hashes",{}).items():
            with self.subTest(path=name):
                self.assertEqual(runner.sha256(self.install/name),expected)

    def test_profile_does_not_inherit_three_floor_burn(self):
        s = load(self.r/"strategy.json")
        p = next(p for p in s["profiles"] if p["id"]=="n1_clear")
        self.assertEqual(p["terminal_rules"],[])
        self.assertEqual(p["failure_action"],"stop_run")
        self.assertNotIn("burn",p["modules"])
        all_modules = {m["id"]:m for m in s["modules"]}
        for mid in p["modules"]:
            self.assertIn(mid,all_modules)
        ms = all_modules["n1_clear_route"]["milestones"]
        for floor in (3,5):
            boss = next(m for m in ms if m["id"]==f"n1_floor{floor}_boss")
            self.assertEqual(boss["enforcement"],"feasible_hard")
            self.assertEqual(boss["floor_window"],[floor,floor])

    def test_original_profiles_preserved(self):
        old = load(PATCH/"base-snapshot/resource/roguelike/BlackFlow/strategy.json")
        new = load(self.r/"strategy.json")
        self.assertEqual(new["profiles"][:-1],old["profiles"])
        self.assertEqual(new["modules"][:len(old["modules"])],old["modules"])

    def test_node_shop_intent_is_wired(self):
        node = load(self.r/"node_execution.json")
        route = next(r for r in node["routes"] if r["id"]=="n1_shop_purchase")
        self.assertEqual(route["task"],runner.PREFIX+"Page-Purchase")
        self.assertEqual(route["floor_window"],[1,5])
        self.assertNotIn("Investment",route["task"])

    def test_no_account_tasks_can_be_queued(self):
        params = runner.task_params(load(PATCH/"settings.json"))
        self.assertEqual(params["theme"],"BlackFlow")
        self.assertEqual(params["difficulty"],1)
        self.assertFalse(params["investment_enabled"])
        self.assertEqual(params["starts_count"],1)
        self.assertFalse(params["stop_at_final_boss"])
        self.assertEqual(params["mode"],0)
        self.assertEqual(params["blackflow_strategy"],"n1_clear")

    def test_remote_devices_are_rejected(self):
        config = load(PATCH/"settings.json")
        config["address"] = "192.168.1.100:5555"
        with self.assertRaises(ValueError):
            runner.task_params(config)

    def test_all_three_starts_borrow_the_first_operator(self):
        config = load(PATCH/"settings.json")
        battle_data = load(self.install/"resource/battle_data.json")
        before = copy.deepcopy(config)
        for start, name in runner.START_OPERATORS.items():
            with self.subTest(start=start):
                params = runner.task_params(config,start)
                self.assertEqual(params["core_char_list"][0],{"name":name,"use_support":True})
                self.assertFalse(any(o["use_support"] for o in params["core_char_list"][1:]))
                self.assertEqual(len(params["core_char_list"]),3)
                self.assertEqual(params["blackflow_strategy"],"n1_clear")
                runner.validate_start_roles(params,battle_data)
        self.assertEqual(config,before)

    def test_start_flag_overrides_config_default(self):
        config = load(PATCH/"settings.json")
        config["default_start"] = "wang"
        self.assertEqual(runner.task_params(config)["core_char_list"][0]["name"],"望")
        self.assertEqual(runner.task_params(config,"mechanist")["core_char_list"][0]["name"],"机械师")

    @unittest.skipUnless(os.name == "nt", "Windows live entry")
    def test_all_live_entries_reject_an_open_gui_before_loading_core(self):
        for start in runner.START_OPERATORS:
            with self.subTest(start=start), mock.patch.object(runner.sys,"argv",["runner.py","--run","--start",start,"--config",str(PATCH/"settings.example.json")]), \
                    mock.patch.object(runner,"read_json",side_effect=lambda path: load(path)), \
                    mock.patch.object(runner,"installation_root",return_value=self.install), \
                    mock.patch.object(runner,"check_integrity"), \
                    mock.patch.object(runner,"maa_gui_running",return_value=True), \
                    mock.patch.object(runner,"load_core") as load_core:
                with self.assertRaisesRegex(RuntimeError,"MAA.exe is open"):
                    runner.main()
                load_core.assert_not_called()

    def test_start_name_and_support_types_are_validated(self):
        original = load(PATCH/"settings.json")
        for field,value in (("name","机械师"),("use_support","false")):
            config = copy.deepcopy(original)
            config["start_profiles"]["wang"]["start_opers"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                runner.task_params(config,"wang")
        with self.assertRaises(ValueError):
            runner.task_params(original,"unknown")

    def test_start_professions_must_match_tickets(self):
        config = load(PATCH/"settings.json")
        battle_data = load(self.install/"resource/battle_data.json")
        for start,replacement in (("mechanist","斑点"),("wang","史都华德")):
            changed = copy.deepcopy(config)
            changed["start_profiles"][start]["start_opers"][1]["name"] = replacement
            params = runner.task_params(changed,start)
            with self.subTest(start=start), self.assertRaises(ValueError):
                runner.validate_start_roles(params,battle_data)

    def test_mechanist_does_not_enter_native_lazy_recruit_branch(self):
        config = load(PATCH/"settings.json")
        for squad in ("特勤分队","堡垒战术分队"):
            config["start_profiles"]["mechanist"]["squad"] = squad
            with self.subTest(squad=squad), self.assertRaises(ValueError):
                runner.task_params(config,"mechanist")

    def test_legacy_settings_remain_usable(self):
        config = load(PATCH/"settings.json")
        legacy = {k:v for k,v in config.items() if k not in ("start_profiles","default_start")}
        legacy.update(copy.deepcopy(config["start_profiles"]["wisadel"]))
        self.assertEqual(runner.task_params(config),runner.task_params(legacy))

    def test_original_gui_fallback_is_removed(self):
        tasks = load(PATCH/"resource/tasks/n1_clear.json")
        self.assertEqual(tasks[runner.PREFIX+"Begin"]["next"],[runner.PREFIX+"StartExplore"])
        for name in ("Abandon","AbandonConfirm","ExitThenAbandon","ReturnConfirm","StartUpThemes"):
            t = tasks[runner.PREFIX+name]
            self.assertEqual(t["action"],"Stop")
            self.assertEqual(t["sub"],[])
        self.assertEqual(tasks[runner.PREFIX+"N1DifficultyVerified"]["text"],["1"])
        self.assertEqual(tasks[runner.PREFIX+"GamePass"]["action"],"DoNothing")
        for name in ("StartAction","InBattleFlag"):
            self.assertNotIn(runner.PREFIX+"MissionFailedFlag2",tasks[runner.PREFIX+name]["next"])
            self.assertIn(runner.PREFIX+"N1RunFailed2",tasks[runner.PREFIX+name]["next"])

    def test_group_names_and_fallback_positions(self):
        recruit = load(self.r/"recruitment.json")
        groups = {g["name"] for g in recruit["priority"]}
        self.assertEqual(len(groups),len(recruit["priority"]))
        self.assertEqual([g["name"] for g in recruit["priority"][-2:]], ["其他地面","其他高台"])
        for path in (self.r/"autopilot").glob("*.json"):
            for item in load(path)["deploy_plan"]:
                self.assertTrue(set(item["groups"]).issubset(groups))
        for condition in recruit["team_complete_condition"]:
            self.assertTrue(set(condition["groups"]).issubset(groups))

    def test_new_recruitment_members_exist(self):
        original = load(PATCH/"base-snapshot/resource/roguelike/BlackFlow/recruitment.json")
        names = {o["name"] for g in original["priority"] for o in g["opers"]}
        recruit = load(self.r/"recruitment.json")
        for group in recruit["priority"]:
            if group["name"].startswith("N1"):
                for oper in group["opers"]:
                    with self.subTest(group=group["name"],oper=oper["name"]):
                        self.assertIn(oper["name"],names)

    def test_core_groups_respect_deployment_positions(self):
        recruit = load(self.r/"recruitment.json")
        groups = {g["name"]:{o["name"] for o in g["opers"]} for g in recruit["priority"]}
        self.assertEqual(groups["N1核心高台"],{"维什戴尔","望"})
        self.assertIn("机械师",groups["N1开场阻挡"])
        self.assertIn("机械师",groups["N1持续阻挡"])
        for path in (self.r/"autopilot").glob("*.json"):
            plan = load(path)
            deployed = {name for slot in plan["deploy_plan"] for group in slot["groups"] for name in groups[group]}
            self.assertIn("机械师",deployed)
            if plan["stage_name"] != "生存习性":
                self.assertTrue({"维什戴尔","望"}.issubset(deployed))

    def test_core_skills_have_elite_one_fallbacks(self):
        expected = {"维什戴尔":(3,2),"望":(3,2),"机械师":(2,1)}
        effective = {}
        for group in load(self.r/"recruitment.json")["priority"]:
            for oper in group["opers"]:
                effective.setdefault(oper["name"],{}).update(oper)
        for name,(skill,alternate) in expected.items():
            with self.subTest(name=name):
                self.assertEqual(effective[name]["skill"],skill)
                self.assertEqual(effective[name]["alternate_skill"],alternate)
                self.assertTrue(effective[name]["is_start"])
                self.assertTrue(effective[name]["is_key"])

    def test_all_deployments_and_homes_are_legal_on_all_variants(self):
        tiles = self.install/"resource/Arknights-Tile-Pos"
        overview = load(tiles/"overview.json")
        directions = {"left","right","up","down"}
        for plan in load(PATCH/"stage-plans.json"):
            variants = [v for v in overview.values() if v["name"]==plan["name"] and v["stageId"].startswith("ro6_")]
            self.assertTrue(variants)
            for v in variants:
                tile = load(tiles/v["filename"])
                for g,x,y,d in plan["slots"]:
                    with self.subTest(stage=plan["name"],variant=v["stageId"],group=g,location=[x,y]):
                        self.assertIn(d,directions)
                        self.assertTrue(0 <= x < tile["width"] and 0 <= y < tile["height"])
                        permitted = {2,3} if g in ("W","M","C","R") else {1,3}
                        self.assertIn(tile["tiles"][y][x]["buildableType"],permitted)
                for x,y,d in plan["homes"]:
                    self.assertIn(d,directions)
                    self.assertTrue(0 <= x < tile["width"] and 0 <= y < tile["height"])
                    self.assertIn(tile["tiles"][y][x]["buildableType"],{1,3})

    def test_all_normal_floors_one_to_five_have_explicit_plans(self):
        overview = load(self.install/"resource/Arknights-Tile-Pos/overview.json")
        required = {v["name"] for v in overview.values()
                    if any(v["stageId"].startswith(f"ro6_n_{f}_") for f in range(1,6))}
        supplied = {p["name"] for p in load(PATCH/"stage-plans.json")}
        self.assertTrue(required.issubset(supplied))
        self.assertTrue({"铁腕迷思","光荣远征","狂热敬虔","永无安宁"}.issubset(supplied))

    def test_builder_is_deterministic(self):
        base = load(PATCH/"base-snapshot/resource/roguelike/BlackFlow/strategy.json")
        before = copy.deepcopy(base)
        a = build_patch.make_strategy(base)
        self.assertEqual(base,before)
        self.assertEqual(a,build_patch.make_strategy(base))

    def test_public_compatibility_metadata_has_no_local_configuration(self):
        metadata = load(PATCH/"compatibility.json")
        self.assertNotIn("install_root",metadata)
        self.assertNotIn("base_hashes",metadata)
        self.assertTrue(all(len(v)==64 for v in metadata["required_hashes"].values()))
        self.assertTrue(all(not k.startswith("config/") for k in metadata["required_hashes"]))

    def test_installation_path_is_explicit_and_portable(self):
        with mock.patch.dict(os.environ,{},clear=True):
            with self.assertRaises(ValueError):
                runner.installation_root({}, {})
            self.assertEqual(runner.installation_root({"maa_install_root":str(PATCH)},{}),PATCH.resolve())


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),
              "successful":result.wasSuccessful(),"device_connected":False,"combat_tested":False}
    (PATCH/"test-report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
