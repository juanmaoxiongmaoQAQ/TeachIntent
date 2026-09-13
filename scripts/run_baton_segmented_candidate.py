#!/usr/bin/env python3
"""Execute one saved Speech Plan through the experimental segmented renderer.

This command DOES synthesize audio. Use the same BATONVOICE_* environment as
the isolation experiment, with BATONVOICE_SPEECH_SPEED=0.85. No planner, web
server, API credentials, retries or waveform processing are involved. Backend
reuse and cleanup belong to SegmentedBatonVoiceRenderer.render().
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from teachintent.renderers.batonvoice import BatonVoiceConfig
from teachintent.renderers.batonvoice_segmented import (
    DEFAULT_OUTPUT_ROOT,
    SegmentedBatonVoiceRenderer,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "cases/baton_diagnostic/golden_case_1_v0_4.speech_plan.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT,
                        help="Must resolve inside TeachIntent; enforced by the renderer")
    parser.add_argument("--prompt-version", default="v0.4", help="Saved-plan provenance only")
    args = parser.parse_args(argv)
    try:
        plan = json.loads(args.plan.read_bytes())
        config = BatonVoiceConfig.from_env()
        if config.speech_speed != 0.85:
            print("This experiment requires BATONVOICE_SPEECH_SPEED=0.85.", file=sys.stderr)
            return 2
        run_dir, manifest = SegmentedBatonVoiceRenderer(config).render(
            speech_plan=plan, prompt_version=args.prompt_version, output_root=args.output_root,
        )  # render() already performs cleanup, including failure/interrupt paths.
        print(run_dir)
        print(f"status: {manifest['status']}", file=sys.stderr)
        return 0 if manifest["status"] == "success" else 1
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Candidate setup failed ({type(exc).__name__}); check the plan, output path and BATONVOICE_* settings.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
