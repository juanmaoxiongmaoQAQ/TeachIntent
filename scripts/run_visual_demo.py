#!/usr/bin/env python3
"""Launch the offline-first TeachIntent Gradio demonstration."""

from __future__ import annotations

import argparse
import inspect
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

from teachintent.visual_demo import DEFAULT_AUDIO_ROOT, DEMO_CSS, build_gradio_app

REPO_ROOT = Path(__file__).resolve().parent.parent


def _probe_startup_events(host: str, port: int) -> bool:
    probe_host = "127.0.0.1" if host == "0.0.0.0" else host
    url = f"http://{probe_host}:{port}/gradio_api/startup-events"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def _hold_server() -> None:
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the TeachIntent visual demo.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--audio-root", type=Path, default=DEFAULT_AUDIO_ROOT)
    parser.add_argument(
        "--share",
        action="store_true",
        help="Ask Gradio for a public share link (off by default).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv(REPO_ROOT / ".env")
    try:
        app = build_gradio_app(audio_root=args.audio_root)
    except RuntimeError as exc:
        print(f"Visual demo unavailable: {exc}", file=sys.stderr)
        return 1
    launch_kwargs = {
        "server_name": args.host,
        "server_port": args.port,
        "share": args.share,
    }
    if "css" in inspect.signature(app.launch).parameters:
        launch_kwargs["css"] = DEMO_CSS
    try:
        app.launch(**launch_kwargs)
    except Exception as exc:
        message = str(exc)
        if "gradio_api/startup-events" not in message:
            raise
        if not _probe_startup_events(args.host, args.port):
            raise
        print(
            "Gradio reported a startup-events health-check failure, but the "
            "local demo endpoint is serving. Keeping the demo running.",
            file=sys.stderr,
        )
        _hold_server()
    return 0


if __name__ == "__main__":
    sys.exit(main())
