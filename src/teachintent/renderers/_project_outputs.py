"""Output containment for experimental TeachIntent renderers."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def project_output_root(path: Path) -> Path:
    """Reject escapes (including existing symlinks) before creating anything."""
    path = Path(path).expanduser()
    resolved = (path if path.is_absolute() else PROJECT_ROOT / path).resolve()
    if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError("Experimental outputs must remain inside the TeachIntent project")
    return resolved
