#!/usr/bin/env python3
"""Render a neutral/planned Qwen3-TTS A/B pair from an existing example."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from teachintent.demo import EXAMPLE_FILES, PUBLIC_PROMPT_VERSIONS, load_recorded_example
from teachintent.renderers.qwen3_tts import (
    DEFAULT_QWEN3_TTS_MODEL,
    Qwen3CustomVoiceBackend,
    Qwen3TTSDependencyError,
    TTSRenderError,
    render_ab_comparison,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate neutral.wav and planned.wav with identical words, voice, "
            "model, and seed; only the Qwen3-TTS instruct value differs."
        )
    )
    parser.add_argument(
        "--example",
        choices=sorted(EXAMPLE_FILES),
        default="corrective-feedback",
    )
    parser.add_argument(
        "--prompt-version", choices=PUBLIC_PROMPT_VERSIONS, default="v0.2"
    )
    parser.add_argument("--speaker", default="Vivian")
    parser.add_argument("--model", default=None, help="Model ID or local model path.")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--device-map", default=None)
    parser.add_argument(
        "--dtype",
        choices=("float16", "bfloat16", "float32"),
        default=None,
    )
    parser.add_argument("--attn-implementation", default=None)
    parser.add_argument("--seed", type=int, default=20260901)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly allow replacing files in the selected output directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = build_parser().parse_args(argv)
    model_id = args.model or os.environ.get(
        "QWEN3_TTS_MODEL", DEFAULT_QWEN3_TTS_MODEL
    )
    device_map = args.device_map or os.environ.get("QWEN3_TTS_DEVICE", "cuda:0")
    dtype = args.dtype or os.environ.get("QWEN3_TTS_DTYPE", "bfloat16")
    attn = args.attn_implementation or os.environ.get("QWEN3_TTS_ATTN") or None
    output_dir = args.output_dir or (
        REPO_ROOT
        / "results"
        / "tts_demo"
        / args.example
        / args.prompt_version.replace(".", "_")
    )

    try:
        example = load_recorded_example(args.example, args.prompt_version)
        backend = Qwen3CustomVoiceBackend(
            model_id=model_id,
            device_map=device_map,
            dtype=dtype,
            attn_implementation=attn,
        )
        manifest = render_ab_comparison(
            example=example,
            backend=backend,
            speaker=args.speaker,
            output_dir=output_dir,
            seed=args.seed,
            overwrite=args.overwrite,
        )
    except (Qwen3TTSDependencyError, TTSRenderError, OSError, ValueError) as exc:
        print(f"TTS demo render failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(manifest["comparison_statement"])
    print(f"Neutral: {output_dir / 'neutral.wav'}")
    print(f"Planned: {output_dir / 'planned.wav'}")
    print(f"Manifest: {output_dir / 'render_manifest.json'}")
    print(f"Instruction: {manifest['delivery_adapter']['instruct'] or '<empty>'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
