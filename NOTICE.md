# 来源与修改说明

本项目包含 MaaAssistantArknights 的资源衍生文件和离线测试所需的原始公共资源样本。MAA 及其贡献者保留原作品的版权；按原项目 AGPL-3.0-only 许可分发，完整许可见 LICENSE。

- 上游仓库：https://github.com/MaaAssistantArknights/MaaAssistantArknights
- 源码参考提交：`b39e052295eaba8e94b5a03f9fe0f1fe8e978dc1`
- 资源基线：MAA v6.19.0 安装包中的公共资源，SHA-256 记录于 `compatibility.json`。
- 修改日期：2026-10-14。

本项目新增独立启动器、配置命令、N1 路线模块、开局配置、部署表和离线测试；调整招募、购物及任务链。`resource-changes.diff` 记录四份主要资源与基线的差异，`build_patch.py` 提供生成源码。原始任务、招募与地图样本位于 `base-snapshot/resource`，不包含用户配置或游戏账号记录。

关卡路线分析另参考：https://github.com/Kengxxiao/ArknightsGameData 的 `zh_CN/gamedata/levels/obt/roguelike/ro6`。本仓库不包含该游戏数据仓库的完整关卡脚本，也不分发美术、音频或游戏客户端。

这是独立实验项目，不代表 MAA 或《明日方舟》官方。
