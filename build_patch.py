"""Build a version-pinned resource overlay. Never write inside the base resource/config dirs."""
import argparse
import copy
import datetime
import difflib
import hashlib
import json
from pathlib import Path
import shutil

PATCH = Path(__file__).resolve().parent
PROFILE = "n1_clear"
THEME = "BlackFlow@Roguelike@"
STOP = "BlackFlow@RoguelikeControlTaskPlugin-Stop"
VICTORY = THEME + "N1ClearVictory"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def milestone(mid, floors, nodes, count=1, weight=3, **extra):
    return dict(id=mid, kind="preferred", floor_window=floors, rank=0,
                count=count, weight=weight, selector={"node_types": nodes}, **extra)


def make_strategy(base):
    strategy = copy.deepcopy(base)
    modules = {m["id"]: m for m in strategy["modules"]}
    development = copy.deepcopy(modules["ending_development"])
    development["id"] = "n1_development"
    development["description"] = "N1 发育与续航；不依赖未接入编队检测的 basic_e2_team 信号"
    development["rules"] = []
    for reserve in development["reserves"]:
        reserve["release_if"] = {"any":[{"fact":"candidate.node_type","op":"eq","value":n}
                                       for n in ("battle_boss","final")]}
    development["milestones"] = [
        milestone("n1_f1_combat", [1,1], ["battle_normal"], 3, 6),
        milestone("n1_f2_combat", [2,2], ["battle_normal"], 2, 5),
        milestone("n1_employ", [1,4], ["employ"], 4, 6),
        milestone("n1_expedition", [2,4], ["expedition"], 2, 4),
        milestone("n1_events", [1,5], ["incident","wish","rest"], 99, 3),
        milestone("n1_light", [2,4], ["light"], 2, 2, minimum_unknown_nodes_revealed=2),
        milestone("n1_mid_combat", [3,4], ["battle_normal"], 2, 2),
    ]
    strategy["modules"].append(development)
    strategy["modules"].append({
        "id": "n1_clear_route",
        "description": "三层与五层 Boss 为路线约束，结算截图才判定通关",
        "milestones": [
            milestone("n1_floor3_boss", [3,3], ["battle_boss"], weight=20,
                      enforcement="feasible_hard", terminality="is_terminal"),
            milestone("n1_floor5_boss", [5,5], ["battle_boss"], weight=30,
                      enforcement="feasible_hard", terminality="is_terminal"),
        ] + [milestone(f"n1_shop_f{f}", [f,f], ["shop"], weight=4,
                       page_intent="shop.n1_purchase") for f in range(1,6)],
        "shopping_rules": [{"id":"n1_relics", "rank":0,
                            "page_intent":"shop.n1_purchase", "buy_table":"n1_relics"}],
        "rules": [
            {"id":"n1_no_optional_elite", "kind":"prefer", "tier":"risk", "rank":0,
             "candidate_if":{"not":{"fact":"candidate.node_type", "op":"eq", "value":"battle_elite"}}},
            {"id":"n1_no_optional_savage", "kind":"prefer", "tier":"risk", "rank":1,
             "candidate_if":{"not":{"fact":"candidate.node_type", "op":"eq", "value":"battle_savage"}}},
            {"id":"n1_avoid_no_high_ground", "kind":"prefer", "tier":"risk", "rank":2,
             "candidate_if":{"not":{"fact":"candidate.node_name", "op":"eq", "value":"生存习性"}}},
            {"id":"n1_safe_exit", "kind":"prefer", "tier":"strategy_constraint", "rank":0,
             "when":{"any":[{"fact":f, "op":"eq", "value":True}
                              for f in ("floor_development_exhausted","safety_margin_low","force_exit")]},
             "candidate_if":{"any":[{"fact":"candidate.route_node_types", "op":"contains", "value":n}
                                     for n in ("final","battle_boss")]}},
        ],
    })
    strategy["profiles"].append({
        "id": PROFILE, "description":"保密等级 1，完整五层一结局，单次探索，不投资、不三层重开",
        "modules":["common_navigation","n1_development","ending1_scrap_trade","n1_clear_route"],
        "terminal_rules":[], "failure_action":"stop_run",
    })
    return strategy


DP = ["伊内丝","芬","讯使","清道夫","香草","德克萨斯","凛冬","桃金娘","极境"]
BLOCK = ["机械师","山","黍","塞雷娅","斑点","古米","星熊","斩业星熊","米格鲁","蛇屠箱",
         "煌","棘刺","百炼嘉维尔","圣约送葬人","羽毛笔","泡普卡","月见夜"]
MEDIC = ["纯烬艾雅法拉","夜莺","闪灵","白面鸮","流明","安赛尔","芙蓉","苏苏洛",
         "华法琳","蜜莓","桑葚","焰影苇草"]
CASTER = ["逻各斯","澄闪","艾雅法拉","刻俄柏","史都华德","阿米娅","卡达","夜烟"]
SNIPER = ["提丰","新约能天使","能天使","克洛丝","速射手","莱伊","鸿雪","艾丽妮"]
GROUPS = {"D":"N1回费", "E":"N1开场阻挡", "G":"N1持续阻挡", "W":"N1核心高台",
          "M":"N1治疗", "C":"N1术师", "R":"N1副狙击"}


def make_recruitment(base):
    result = copy.deepcopy(base)
    first = {}
    for group in result["priority"]:
        for oper in group["opers"]:
            first.setdefault(oper["name"], oper)
    def update(name, **values):
        if name not in first:
            raise ValueError("Unknown operator: " + name)
        first[name].update(values)
    # Later occurrences inherit/override earlier ones in MaaCore's parser.
    cores = {
        "维什戴尔":dict(skill=3, alternate_skill=2, skill_usage=1, is_start=True,
                      is_key=True, recruit_priority=1100, promote_priority=1200),
        "望":dict(skill=3, alternate_skill=2, skill_usage=1, is_start=True,
                 is_key=True, recruit_priority=1000, promote_priority=1100),
        "机械师":dict(skill=2, alternate_skill=1, skill_usage=1, is_start=True,
                    is_key=True, recruit_priority=910, promote_priority=1000),
    }
    for group in result["priority"]:
        for oper in group["opers"]:
            if oper["name"] in cores:
                values = cores[oper["name"]]
                oper.update(values, recruit_priority_when_team_full=values["recruit_priority"]-100,
                            promote_priority_when_team_full=values["promote_priority"])
    for name in ("逻各斯","伊内丝"):
        update(name, recruit_priority=890, promote_priority=950,
               recruit_priority_when_team_full=690, promote_priority_when_team_full=950)
    for name in ("芬","讯使","清道夫","桃金娘"):
        update(name, recruit_priority=820, recruit_priority_when_team_full=460,
               recruit_priority_offsets=[{"groups":["N1回费"], "threshold":1, "offset":-400}])
    for name in ("斑点","古米","米格鲁","山"):
        update(name, recruit_priority=810, recruit_priority_when_team_full=500,
               recruit_priority_offsets=[{"groups":["N1持续阻挡"], "threshold":2, "offset":-350}])
    update("山", skill=2, skill_usage=2, skill_times=1)
    for name in ("安赛尔","芙蓉","苏苏洛","白面鸮"):
        update(name, recruit_priority=825, recruit_priority_when_team_full=470,
               recruit_priority_offsets=[{"groups":["N1治疗"], "threshold":1, "offset":-400}])
    update("史都华德", recruit_priority=730, is_start=True)
    for name in ("孑","老鲤","琳琅诗怀雅"):
        update(name, recruit_priority=180, recruit_priority_when_team_full=100)
    groups = [("N1核心高台", ["维什戴尔","望"]),
              ("N1回费", DP), ("N1开场阻挡", DP[:7]+["机械师","斑点","古米","米格鲁","山","泡普卡"]),
              ("N1持续阻挡", BLOCK), ("N1治疗", MEDIC), ("N1术师", CASTER),
              ("N1副狙击", [n for n in SNIPER if n in first and n not in ("艾丽妮",)])]
    additions = []
    for name, members in groups:
        opers = [{"name":n, **({"role":"CASTER"} if n=="阿米娅" else {})} for n in members]
        additions.append({"name":name,"opers":opers})
    # MAA reserves the last two groups for unknown melee/ranged operators.
    result["priority"][-2:-2] = additions
    result["team_complete_condition"] = [
        {"groups":["N1核心高台","机械师"],"threshold":1}, {"groups":["N1持续阻挡"],"threshold":2},
        {"groups":["N1治疗"],"threshold":1}, {"groups":["N1回费"],"threshold":1},
    ]
    return result


def make_tasks(base, generic):
    out = {}
    # Settlement's native plugin clicks through automatically on a task named GamePass.
    # The alternate name keeps victory detection read-only and stops on the success page.
    out[VICTORY] = {"baseTask":THEME+"GamePass", "action":"DoNothing", "sub":[], "next":[STOP]}
    for name, alias in (("MissionFailedFlag","N1RunFailed"),("MissionFailedFlag2","N1RunFailed2")):
        out[THEME+alias] = {"baseTask":THEME+name,"action":"DoNothing","sub":[],"next":[STOP]}
    out[THEME+"GamePass"] = {"action":"DoNothing","next":[STOP]}
    out[THEME+"Begin"] = {"next":[THEME+"StartExplore"],"onErrorNext":[STOP]}
    unsafe = ["Abandon","AbandonConfirm","ExitThenAbandon","ExitThenAbandon-Enter",
              "StrategyTerminalAction","ReturnConfirm","StartUpThemes","ClickToStartPoint",
              "ClickToStartPointAfterFailed"]
    for name in unsafe:
        # Keep the inherited recognition algorithm: an unconditional JustReturn in
        # a candidate list would mask valid candidates after it.
        out[THEME+name] = {"action":"Stop","sub":[],"next":[],"onErrorNext":[],"exceededNext":[]}
    aliases = {THEME+"GamePass":VICTORY,THEME+"MissionFailedFlag":THEME+"N1RunFailed",
               THEME+"MissionFailedFlag2":THEME+"N1RunFailed2"}
    for key, value in base.items():
        for field in ("next","onErrorNext","exceededNext"):
            old = value.get(field, [])
            if any(x in aliases for x in old):
                out.setdefault(key,{})[field] = [aliases.get(x,x) for x in old]
    for name in ("GamePassSkip1Confirm","GamePassSkip2","GamePassTheEndConfirm","StartAction","InBattleFlag"):
        value = base.get(THEME+name,{})
        refs = value.get("next", generic.get("Roguelike@"+name,{}).get("next",[]))
        scoped = [THEME+x.removeprefix("Roguelike@") if x.startswith("Roguelike@") else x for x in refs]
        out.setdefault(THEME+name,{})["next"] = [aliases.get(x,x) for x in scoped if not x.endswith("ClickToStartPoint")]
    for name in ("MissionFailedFlag","MissionFailedFlag2"):
        out[THEME+name] = {"action":"DoNothing","next":[STOP]}
    out[THEME+"Stages"] = {"onErrorNext":[THEME+"RecoveryFailed"]}
    # The difficulty selector can silently fall back. Verify exactly 1 before confirming.
    out[THEME+"ChooseDifficultyConfirm"] = {
        "action":"DoNothing","postDelay":0,"next":[THEME+"N1DifficultyVerified"]}
    out[THEME+"N1DifficultyVerified"] = {
        "baseTask":THEME+"ChooseDifficulty_AnalyzeCurrentDifficulty",
        "text":["1"],"fullMatch":True,"action":"DoNothing",
        "next":[THEME+"N1ConfirmDifficulty"],"onErrorNext":[THEME+"N1DifficultyCheckFailed"]}
    original = copy.deepcopy(generic["Roguelike@ChooseDifficultyConfirm"])
    original["next"] = []
    out[THEME+"N1ConfirmDifficulty"] = original
    out[THEME+"N1DifficultyCheckFailed"] = {"algorithm":"JustReturn","action":"Stop"}
    out[THEME+"StartExplore"]= {"preDelay":300,"onErrorNext":[STOP]}
    return out


def build(install):
    if not (install/"MaaCore.dll").is_file():
        raise ValueError("MAA installation not found")
    if install == PATCH or PATCH in install.parents:
        raise ValueError("Patch and base installation must be separate")
    resource = install/"resource"
    relative = Path("resource/roguelike/BlackFlow")
    names = ["strategy.json","recruitment.json","shopping.json","node_execution.json"]
    watched = [install/"MaaCore.dll",install/"MAA.exe",resource/"tasks/Roguelike/base.json",
               resource/"tasks/Roguelike/BlackFlow.json",resource/"Arknights-Tile-Pos/overview.json"]
    watched += [install/relative/n for n in names]
    hashes = {p.relative_to(install).as_posix():digest(p) for p in watched}
    required_hashes = hashes
    compatibility = read(PATCH/"compatibility.json")
    if compatibility["required_hashes"] != required_hashes:
        raise ValueError("This MAA build differs from the checked compatibility baseline; no files were written")
    manifest_path = PATCH/"manifest.json"
    snapshot_hashes = hashes
    if manifest_path.exists():
        previous = read(manifest_path)
        if previous["required_hashes"] != required_hashes:
            raise ValueError("Base resources/core changed since snapshot; create a new patch folder, do not silently rebase")
        snapshot_hashes = previous["base_hashes"]
    for path in watched:
        target = PATCH/"base-snapshot"/path.relative_to(install)
        if path.suffix.lower() == ".json" and not target.exists():
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)
    strategy = make_strategy(read(install/relative/"strategy.json"))
    write(PATCH/relative/"strategy.json",strategy)
    recruit = make_recruitment(read(install/relative/"recruitment.json"))
    write(PATCH/relative/"recruitment.json",recruit)
    shopping = read(install/relative/"shopping.json")
    shopping["buy_tables"]["n1_relics"] = copy.deepcopy(shopping["buy_tables"]["final_relics"])
    write(PATCH/relative/"shopping.json",shopping)
    node = read(install/relative/"node_execution.json")
    node["routes"].append({"id":"n1_shop_purchase","page_intent":"shop.n1_purchase",
                            "node_types":["shop"],"floor_window":[1,5],"rank":0,
                            "alias":THEME+"NodeDispatchAction","task":THEME+"Page-Purchase",
                            "completion_task":THEME+"LegacyCompletion-NodePage"})
    write(PATCH/relative/"node_execution.json",node)
    base_tasks = read(resource/"tasks/Roguelike/BlackFlow.json")
    generic = read(resource/"tasks/Roguelike/base.json")
    tasks = make_tasks(base_tasks,generic)
    write(PATCH/"resource/tasks/n1_clear.json",tasks)
    stages = read(PATCH/"stage-plans.json")
    for stage in stages:
        plan = {"stage_name":stage["name"], "not_use_dice":True,
                "replacement_home":[{"location":[x,y],"direction":d} for x,y,d in stage["homes"]],
                "role_order":["pioneer","sniper","tank","medic","caster","warrior","support","special","drone"],
                "deploy_plan":[{"groups":[GROUPS[g]],"location":[x,y],"direction":d}
                               for g,x,y,d in stage["slots"]]}
        write(PATCH/relative/"autopilot"/(stage["name"]+".json"),plan)
    diffs = []
    for name in names:
        before = (install/relative/name).read_text(encoding="utf-8-sig").splitlines(True)
        after = (PATCH/relative/name).read_text(encoding="utf-8").splitlines(True)
        diffs.extend(difflib.unified_diff(before,after,
                     fromfile="a/"+(relative/name).as_posix(),tofile="b/"+(relative/name).as_posix()))
    (PATCH/"resource-changes.diff").write_text("".join(diffs),encoding="utf-8")
    write(manifest_path,{"patch_id":"blackflow-n1-clear-v2","created_at":datetime.datetime.now().isoformat(),
                         "install_root":str(install),"profile":PROFILE,"base_hashes":snapshot_hashes,
                         "required_hashes":required_hashes,"build_input_hashes":hashes,
                         "stage_count":len(stages),"combat_tested":False,
                         "start_profiles":["wisadel","wang","mechanist"],
                         "upstream_commit":"b39e052295eaba8e94b5a03f9fe0f1fe8e978dc1"})
    if any(digest(install/name)!=value for name,value in hashes.items()):
        raise RuntimeError("An original file changed during build")
    print(f"Built {len(stages)} stage plans; originals unchanged; device not connected.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root",type=Path,required=True)
    args = parser.parse_args()
    build(args.install_root.resolve())
