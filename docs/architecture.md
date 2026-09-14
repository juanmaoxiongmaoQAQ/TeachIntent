# 架构与版本边界

TeachIntent 把教学输入 `(C, P, L, G)` 转为教学语言 `V` 和表达计划 `D`。
Hy3 是规划器；独立质量检查读取输入和计划；可选语音适配器负责执行计划。

| 层 | 实现 | 职责 |
|---|---|---|
| 产品网页 | `frontend/src/pages/`、`components/product/` | 中文输入、教学步骤、质量检查、可选音频 |
| 应用与接口 | `src/teachintent/app_service.py`、`web_api.py` | 示例读取、会话、显式生成/检查/渲染 |
| 规划 | `src/teachintent/generator/`、`prompts/` | Hy3 请求、版本选择、解析 |
| 契约 | `schemas/`、`models/`、`validators/` | JSON Schema 和跨字段校验 |
| 质量检查 | `src/teachintent/evaluator/` | 六维判断、证据定位和合法性检查 |
| 语音 | `src/teachintent/renderers/`、`adapters/` | 保守映射与可选语音执行 |

首页 `/` 解释产品；`/studio` 处理一次教学回应；`/examples` 读取三个已保存案例。
`/compare` 是二级高级入口。旧 `/live`、`/explore`、`/showcase` 路由兼容保留。
示例填充只读输入，生成、质量检查、语音执行分别由用户触发。

输入契约为 `1.0.0-rc.2`，Speech Plan 为 `1.0.0-rc.3`，Evaluator 为 v0.1。
生成器库默认 Prompt v0.1；网页默认 v0.2，对比固定 v0.2。
v0.3/v0.4 只能在在线体验的技术详情中显式选择。
正式 v0.2 与冻结的 v0.2-rc.2 模型输入保持字节一致。
示例库保留真实 v0.2 来源，不能重标为 v0.4。

前端中文展示只转换标签，不修改输入含义、输出文本、证据内容或后端契约。
表达提示继承全局控制，同名局部控制覆盖全局值；没有控制时明确显示无需额外控制。
质量摘要按原始评分概括，完整理由和证据可主动展开；它不替代原始 Judge 判断。
技术详情统一收纳原始 JSON、版本、会话、映射与错误。

见 [Speech Plan 契约](speech_plan_schema.md)、[评价方法](EVALUATION_METHOD.md)、
[语音执行边界](renderer.md) 和 [测试边界](TESTING.md)。
