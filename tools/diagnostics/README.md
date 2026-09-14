# 研发诊断工具

此目录保存 Baton 分段、隔离和重复性诊断入口，用于研发复现，不属于
Quick Start，也不影响核心产品运行。脚本只调用既有实现；本次整理未改变
映射、采样、渲染或失败处理。离线测试仍检查这些入口。

| 工具 | 用途 |
|---|---|
| `run_baton_segmented_candidate.py` | 对已保存的 Speech Plan 执行一次分段渲染 |
| `diagnose_baton_segment_isolation.py` | 分段隔离诊断 |
| `diagnose_baton_seg04_repeatability.py` | 固定 high condition 的重复性诊断 |
| `diagnose_baton_seg04_neutral_repeatability.py` | 固定 neutral condition 的重复性诊断 |

从仓库根目录运行 `python tools/diagnostics/<脚本名> --help` 查看参数。
真实执行需要独立配置环境并获得相应实验授权；网页验收不运行这些实验。
输出仍限定在项目内部 `outputs/`，不纳入 Git。

旧文档或日志中的同名 `scripts/` 路径对应此目录。Pilot、生成器基线与
评价器协议的复现入口继续保留在 `scripts/`，以维持冻结协议中的命令路径；
它们也不属于产品启动链路。两个未跟踪的 retired K0 文件不纳入此目录或发布。
