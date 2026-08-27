# TeachIntent

> **个人 / 活动作品**：本项目基于 Hy3 构建，用于相关开源实战活动，不代表腾讯官方发布。

TeachIntent 是一个面向智能教育场景的 **Pedagogical Intent Driven Speech Planning** 原型系统。

项目关注的问题是：

> 给定教学内容、教学情境、学习者状态和明确的教学意图，AI 应该“说什么”，以及“应该怎样表达”。

与直接生成普通文本或最终语音不同，TeachIntent 在教学决策与语音生成之间加入一个结构化的 **Speech Plan** 层，将教师话语内容与表达控制显式化，并进一步对生成结果进行自动验证和教学层面的诊断评估。

## 项目方案

完整的阶段性项目方案见：

👉 [PROPOSAL.md](./PROPOSAL.md)

其中包含项目的：

* 设计思路
* 总体架构
* 重点技术
* 预期效果
* 实验与验证计划
* 时间规划

## 核心流程

```text
教学内容 / 教学情境 / 学习者状态 / 教学意图
                    │
                    ▼
              Input Contract
                    │
                    ▼
              Hy3 Speech Planner
                    │
                    ▼
             Structured Speech Plan
             ├─ Verbal Plan
             └─ Delivery Plan
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
   Contract Validation   Pedagogical Evaluation
          │                   │
          └─────────┬─────────┘
                    ▼
             Diagnostic Results
```

当前项目主要聚焦 **Speech Planning 与 Evaluation**，暂不绑定某一种具体 TTS 引擎。

## 当前能力

当前版本已实现：

* 教学场景结构化输入；
* 教学意图驱动的 Speech Plan 生成；
* Verbal Plan 与 Delivery Plan 的结构化表示；
* JSON Schema 与 Pydantic 双层契约验证；
* Hy3 / OpenRouter 调用链路；
* Controlled、Cross-domain、Hard / Adversarial 三类 Pilot Cases；
* 自动化 Pilot Runner 与实验结果记录；
* 面向教学语音规划的诊断式评价框架设计。

## 项目结构

```text
TeachIntent/
├── README.md
├── PROPOSAL.md
├── cases/              # Pilot cases
├── docs/               # Research specifications
├── schemas/            # JSON Schema contracts
├── scripts/            # Validation / experiment scripts
├── src/teachintent/    # Core implementation
└── tests/              # Automated tests
```

生成结果与本地实验产物不会提交至公开仓库。

## 环境要求

推荐：

```text
Python >= 3.10
```

安装项目与开发依赖：

```bash
python -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

## 配置 Hy3

复制环境变量模板：

```bash
cp .env.example .env
```

然后在本地 `.env` 中配置：

```text
HY3_API_KEY=your_api_key
HY3_BASE_URL=https://openrouter.ai/api/v1
HY3_MODEL=tencent/hy3
```

`.env` 已被 Git 忽略。

**请勿将 API Key、Authorization Header 或其他密钥提交至仓库。**

## 运行测试

```bash
.venv/bin/pytest -q
```

## Pilot Dataset 验证

例如验证 Pilot Case Dataset：

```bash
.venv/bin/python scripts/validate_pilot_cases.py \
  cases/pilot/blocks/block_c_hard_adversarial.jsonl
```

验证过程包括：

* JSON 解析；
* JSON Schema 验证；
* Pydantic 验证；
* Dataset-level consistency checks。

## 运行 Pilot

在完成 Hy3 环境配置后，可以通过对应脚本运行实验，例如：

```bash
.venv/bin/python scripts/run_pilot_block_c.py
```

实验结果默认写入本地 `results/` 目录，该目录不纳入公开 Git 仓库。

## 项目状态

当前项目处于活动开发阶段。

截至方案提交阶段，已完成核心 Speech Planning Pipeline、可执行契约、Pilot Dataset 与基线实验，后续将重点完善 Evaluator、评价验证与最终 Demo。

详细开发安排见 [PROPOSAL.md](./PROPOSAL.md)。

## Security

本项目不在代码中硬编码任何 API Key。

如发现本地配置中包含敏感信息，请确认：

```text
.env
results/
```

等文件或目录未被提交至 Git。

## License / Disclaimer

本项目为个人研究与活动作品，主要用于教学语音规划与评价方法的探索。

项目中对 Hy3 的使用仅代表本项目自身的应用实践，不代表腾讯官方立场或官方发布。
