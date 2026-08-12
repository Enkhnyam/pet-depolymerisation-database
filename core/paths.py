"""Central paths. Pushable source lives at the project root; everything we can't
push (copyrighted data + generated output) lives under artifacts/, git-ignored."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

ARTIFACTS = ROOT / "artifacts"
DATA_DIR = ARTIFACTS / "data"       # curated paper inputs (copyright)
RUNS_DIR = ARTIFACTS / "runs"       # run bundles

PROMPTS_DIR = ROOT / "prompts"
ABLATION_CONFIGS_DIR = ROOT / "configs" / "extract"

def resolve(path_like: str) -> Path:
    """A pushable, root-relative path (prompts, licenses.json)."""
    p = Path(path_like)
    return p if p.is_absolute() else ROOT / p


def data_path(name: str) -> Path:
    """A curated-data filename under artifacts/data/."""
    p = Path(name)
    return p if p.is_absolute() else DATA_DIR / p


def prompt_path(name: str) -> Path:
    """A prompt filename under prompts/."""
    p = Path(name)
    return p if p.is_absolute() else PROMPTS_DIR / p


def output_root(output_dir: str | None) -> Path:
    """A config's run bundles land in artifacts/runs/<output_dir>/ (or runs/ if unset)."""
    if not output_dir:
        return RUNS_DIR
    p = Path(output_dir)
    return p if p.is_absolute() else RUNS_DIR / p
