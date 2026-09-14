# TeachIntent 开发交接

当前产品入口为首页 `/`、在线体验 `/studio` 和示例库 `/examples`；
教学意图对比 `/compare` 是高级功能。旧路由保留兼容跳转。

开始工作时先读仓库 `AGENTS.md`，检查 Git 状态和日志，再按任务阅读冻结协议。
仓库实际内容是最终依据；不要按旧交接记录启动新的实验。

- [快速开始与产品说明](../README.md)
- [架构与版本边界](architecture.md)
- [离线测试与历史证据边界](TESTING.md)
- [可选语音执行](renderer.md)
- [第三方组件与音频来源](THIRD_PARTY.md)
- [研发诊断工具](../tools/diagnostics/README.md)

冻结协议、Prompt、Schema、评价准则和已记录实验结果仍受 AGENTS.md 约束。
示例库读取三个已有 v0.2 案例及六个已获项目所有者公开授权的合成 WAV，
不能把这些记录改写为新版本结果。质量检查针对计划，不能据此宣称音频质量。

`scripts/start_showcase.sh` / `stop_showcase.sh` 是兼容保留的本地服务工具，
仅管理自身启动的进程，状态和日志写入忽略的 `outputs/showcase-runtime/`。
真实服务调用需显式用户操作；离线测试与网页验收使用假客户端或冻结数据。

两个本地 retired K0 脚本继续保持未跟踪，不能删除或纳入发布。
生成产物、缓存、模型、真实环境变量和历史实验数据不进入 Git。
