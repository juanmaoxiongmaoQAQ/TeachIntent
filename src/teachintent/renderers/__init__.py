"""Optional downstream renderers for validated TeachIntent Speech Plans."""

from .qwen3_tts import (
    DEFAULT_QWEN3_TTS_MODEL,
    Qwen3CustomVoiceBackend,
    Qwen3TTSDependencyError,
    Qwen3TTSInstruction,
    TTSRenderError,
    build_qwen3_tts_instruction,
    qwen_language_from_bcp47,
    render_ab_comparison,
    verbal_text_from_plan,
)

__all__ = [
    "DEFAULT_QWEN3_TTS_MODEL",
    "Qwen3CustomVoiceBackend",
    "Qwen3TTSDependencyError",
    "Qwen3TTSInstruction",
    "TTSRenderError",
    "build_qwen3_tts_instruction",
    "qwen_language_from_bcp47",
    "render_ab_comparison",
    "verbal_text_from_plan",
]
