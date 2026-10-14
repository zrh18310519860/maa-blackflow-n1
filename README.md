# MAA 黑流树海 N1 探索补丁

面向 MAA v6.19.0 的独立资源覆盖补丁，尝试完成《明日方舟》黑流树海保密等级 1 的五层一结局。

**实验项目，未实战验证，不保证通关。** 已验证资源加载、任务参数和离线测试；尚无完整 N1 通关记录。此项目独立于 MAA 官方维护。

## 功能

- 独立 `n1_clear` 路线，固定难度 1、单次探索，不继承三层退出或重开策略，不投资。
- 三层及五层 Boss 为可行时必达目标，商店购物与发育节点接入原内核路线规划。
- 33 张部署表：29 个常规关卡及铁腕迷思、光荣远征、狂热敬虔、永无安宁；检查同名紧急地图的部署格。
- 支持维什戴尔、望、机械师三种开局，默认第一顺位借好友助战。未收到助战确认回调时停止。
- 只有本次策略初始化、难度验证、最终战结束和胜利页识别都满足，才记录通关。
- 出错时停止输入，不自动放弃、退出肉鸽或重开；仅提交 `Roguelike` 任务，没有寻访任务。
- 通过模拟器 ADB/MaaTouch 输入，不接管 Windows 鼠标或键盘。

## 开局配置

| 启动入口 | 第一顺位助战 | 另外两位自有干员 | 分队 | 职业组 |
| --- | --- | --- | --- | --- |
| `Start-N1.cmd` | 维什戴尔 | 斑点、史都华德 | 远程战术分队 | 稳扎稳打 |
| `Start-N1-Wang.cmd` | 望 | 芬、克洛丝 | 指挥分队 | 先手必胜 |
| `Start-N1-Mechanist.cmd` | 机械师 | 史都华德、安赛尔 | 指挥分队 | 坚不可摧 |

维什戴尔和望使用高台部署位；机械师使用地面阻挡位。维什戴尔、望默认三技能，未精二时备选二技能；机械师使用二技能。实际能否借到对应干员由游戏助战列表决定，离线参数通过不代表助战可用。

机械师开局使用指挥分队，避开当前内核在模式 0 配合特勤/堡垒分队时跳过其他初始招募的分支；不会预设借来的机械师已精二或必有结构性原理。望的棋子仍由通用部署处理，没有专门的落子和回收时序。

## 环境

- Windows x64、64 位 Python 3.10+；无需额外 Python 包。
- MAA v6.19.0，基础程序及资源必须匹配 `compatibility.json`。目前只核对这一版本和资源组合，更新版会拒绝加载，需要重新适配。
- 已打开的 MuMu 模拟器和《明日方舟》，可用的本地 ADB 端口。
- 已解锁所选分队，好友助战及另外两名自有干员满足要求。

本仓库不分发 MAA 可执行程序、模拟器、游戏程序或账号数据。

## 配置和运行

在项目目录的 PowerShell 中执行，参数换为自己的安装路径和端口：

```powershell
python configure.py --install-root 'D:\Apps\MAA' --adb-path 'D:\Apps\MuMu\adb.exe' --address '127.0.0.1:16384'
python -B test_patch.py
powershell -NoProfile -ExecutionPolicy Bypass -File .\Check-Starts.ps1
```

配置命令生成本地 `settings.json` 和 `manifest.json`，并从版本一致的原资源重建覆盖文件。它不会连接设备或启动游戏任务，也不会写入原 MAA 的程序、配置或资源目录。

游戏停在黑流树海常规行动的开始探索页。手动处理旧探索，补丁不会自动放弃。关闭原 `MAA.exe`，保留模拟器和游戏，然后选择上表的启动入口。通用入口默认维什戴尔；也可执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-N1.ps1 -Run -Start wang
```

`-Start` 可为 `wisadel`、`wang`、`mechanist`。不加 `-Run` 默认只离线检查。Python 不在 PATH 时，用环境变量 `MAA_N1_PYTHON` 指向解释器。

本地 `settings.json` 可调整 `default_start`、助战开关、分队、另外两名干员与时限；开局职业必须互异且匹配所选职业组。默认 `use_nonfriend_support: false`，只借好友。`MAA_INSTALL_ROOT` 可临时覆盖 MAA 安装路径。

停止输入：控制台按 `Ctrl+C`，或执行 `Stop-N1.ps1`。后者在 `runtime` 写停止标记；确认游戏状态后移除 `runtime/stop.request` 才能再次运行。停止输入不等于暂停战斗，需要在模拟器中手动暂停。

## 验证和限制

- 2026-10-14，本地 MaaCore v6.19.0 接受三套开局参数并初始化 `n1_clear`；检查时未连接设备、未启动任务。
- 离线测试涵盖地图可部署性、职业匹配、招募分组、难度和通关判定、GUI 冲突检查及版本完整性。
- 地图格合法、资源加载成功都不证明战斗能赢。技能沿用可用就用逻辑，没有精确时序；特殊事件战、对决、强化 Boss 使用原通用战斗逻辑。
- 生存习性没有高台，路线会尽量避开；望的棋子、复杂敌人机制和治疗覆盖仍需实战调试。
- 单场战斗默认上限 420 秒，整局 180 分钟。只在结果 JSON 的 `completed` 为 `true` 且结算画面一致时视为通关。
- `runtime/result-*.json`、事件记录和原生日志只保存在本地，不会提交到仓库。

## 开发

```powershell
python -B test_patch.py
python build_patch.py --install-root 'D:\Apps\MAA'
```

不安装 MAA 也可以运行离线测试：测试使用 `base-snapshot/resource` 中的公共资源样本；需要原生 Windows 或实际安装的检查会明确跳过。CI 在 Windows 和 Linux 上运行离线测试。

主要文件：`stage-plans.json` 是部署源数据，`build_patch.py` 生成资源覆盖层，`runner.py` 调用官方 Python API，`configure.py` 生成本机配置。修改策略后应重新生成资源、运行测试，再单独做实战验收。

## 许可和来源

采用 **AGPL-3.0-only**，见 [LICENSE](LICENSE)。原 MAA 资源的作者归属及参考提交见 [NOTICE.md](NOTICE.md)。衍生资源、原始公共资源样本和生成代码一并公开。

MAA 上游：[MaaAssistantArknights/MaaAssistantArknights](https://github.com/MaaAssistantArknights/MaaAssistantArknights)，源码参考提交 `b39e052295eaba8e94b5a03f9fe0f1fe8e978dc1`。关卡路径分析参考 [Kengxxiao/ArknightsGameData](https://github.com/Kengxxiao/ArknightsGameData) 中 `zh_CN/gamedata/levels/obt/roguelike/ro6`。

不要提交 `settings.json`、本机 manifest、MAA 的 GUI 配置、截图或日志；这些已列入 `.gitignore`。问题反馈请参考 [CONTRIBUTING.md](CONTRIBUTING.md)。
