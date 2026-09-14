# 可选语音执行

语音是教学计划的可选执行结果。计划质量检查评估 Speech Plan，不评价音频，
也不是生成音频的强制前置条件。没有语音环境时仍可使用示例库和教学规划。

网页默认按需使用实验性分段执行：每个 verbal segment 独立生成 WAV，
浏览器按原始顺序播放。没有 WAV 拼接、插入静音、交叉淡化、重试或 ASR 兜底。
这不承诺无缝播放、准确停顿时长或精确词级韵律。生成失败的分段不会自动跳过。
整段执行方式保留在技术详情中，不改变原有 API。

服务端变量如下，仅填写已有本地资源路径；真实 `.env` 不进入 Git。

| 变量 | 用途 / 参考值 |
|---|---|
| `BATONVOICE_MODEL_PATH` | 已有 Baton checkpoint |
| `BATONVOICE_COSYVOICE_MODEL_DIR` | 已有 CosyVoice2 checkpoint |
| `BATONVOICE_SOURCE_DIR` | Tencent BatonVoice 源码目录 |
| `BATONVOICE_WETEXT_FST_DIR` | WeText FST 资源目录 |
| `BATONVOICE_PROMPT_AUDIO_PATH` | 有权使用的参考录音 |
| `BATONVOICE_TENSOR_PARALLEL_SIZE` | `1` |
| `BATONVOICE_GPU_MEMORY_UTILIZATION` | `0.25` |
| `BATONVOICE_FP16` | `0` |
| `BATONVOICE_SPEECH_SPEED` | `0.85`，保留已有参考条件 |
| `TEACHINTENT_BATONVOICE_OUTPUT_DIR` | 整段执行根目录，默认项目内 `outputs` |

分段 Web 输出位于项目内 `outputs/baton-segmented/`，诊断工具也限制项目内输出。
路径和权重不随源码分发。配置过程不属于无需模型的 Quick Start。

三个公开示例的六个合成 WAV 实际来自 Qwen3-TTS，页面称“基础语音”和
“规划后语音”，明确注明已有音频；它们不是实时 Baton 结果。
支持性反馈的空 delivery plan 对应相同 A/B 文件，不宣称可听差异。

更完整的研发记录见 [分段设计](batonvoice_segmented_candidate.md)、
[实验性 Web 集成](batonvoice_segmented_web.md)、
[诊断工具](../tools/diagnostics/README.md) 和 [第三方来源](THIRD_PARTY.md)。
