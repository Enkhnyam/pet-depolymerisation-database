"""Copy the inputs that cannot be recreated into artifacts/backup/, which is the only part of
artifacts/ that git tracks.

The rule this file exists to enforce: source and irreplaceable input go to GitHub, generated
output does not. artifacts/ holds both, mixed together, and 118 MB of it was tracked -- 64 MB of
converted publisher text among it, which core/paths.py and .gitignore both already said must not
be pushed.

So the split is drawn by what could be produced again from what is pushed:

  KEEP     the LLM runs' own output, the hand-curated answer key, the chemists' decisions, the
           Scopus funnel, and the Gao comparison's primary CSVs. None of it can be recomputed.
           A run's config could in principle produce another run, but not *this* run: the models
           are nondeterministic and the calls were paid for, so the output is primary data.

  DROP     everything a script in this repository writes: the figures, the macro file, the
           release workbooks, the review and adjudication HTML, and the runs' raw/ directories
           -- 458 MB of API responses that no check opens. Also the converted corpus: 64 MB of
           publishers' full text, which is not ours to redistribute and which the funnel numbers
           are the only claims resting on.

--check is what keeps the promise honest. It re-derives the KEEP set and fails if a file the
checks declare is missing from the backup, so "this is enough to rebuild the paper" is a tested
statement rather than an assurance.

    backup.py            refresh artifacts/backup/
    backup.py --check    fail if the backup is missing or stale
    backup.py --restore  copy it back over artifacts/, for a fresh clone
"""
import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
BACKUP = ARTIFACTS / "backup"

# Globs are relative to artifacts/. The backup mirrors these paths exactly, so restoring is a
# copy and not a mapping anyone has to remember.
KEEP = [
    # --- the runs: what the models wrote, and what each run was ---
    "runs/**/run_meta.json", "runs/**/judge_meta.json", "runs/**/config.json",
    "runs/**/eval.json", "runs/**/labels.json",
    "runs/**/extractions/*.json", "runs/**/verdicts/*.json",
    # --- the answer key, and the papers it was built from ---
    "data/curated_table_final.json", "data/curated_data_markdown_by_doi/*",
    # --- the chemists' work: decisions only, not the HTML they were made in ---
    "gold/decisions/*", "gold/*.json", "gold/README.md",
    "gold/source_run/labels.json", "gold/source_run/eval.json",
    "gold/source_run/config.json", "gold/source_run/extractions/*.json",
    # --- the funnel, and the third-party set we are compared against ---
    "data/corpus_candidates.csv", "data/source_format.csv", "data/gao/*",
]


def wanted() -> list[Path]:
    found: set[Path] = set()
    for pattern in KEEP:
        found |= {p for p in ARTIFACTS.glob(pattern) if p.is_file()}
    return sorted(found)


def refresh() -> tuple[int, int]:
    copied = 0
    for source in wanted():
        target = BACKUP / source.relative_to(ARTIFACTS)
        if target.exists() and filecmp.cmp(source, target, shallow=False):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1

    # A file dropped from KEEP, or deleted upstream, should leave the backup too: a backup that
    # only ever grows stops being a statement about what the paper needs.
    live = {BACKUP / p.relative_to(ARTIFACTS) for p in wanted()}
    stale = 0
    for path in sorted(BACKUP.rglob("*"), reverse=True):
        if path.is_file() and path not in live:
            path.unlink()
            stale += 1
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    return copied, stale


def missing() -> list[str]:
    """Declared inputs that the backup does not hold. Empty list means it can rebuild."""
    sys.path.insert(0, str(ROOT / "checks"))
    from _setup import CURATED, DATABASE, DATABASE_JUDGE, EXTRACTION, JUDGE, data_path

    gaps = []
    for run in (DATABASE, DATABASE_JUDGE, EXTRACTION, JUDGE):
        for part in ("extractions/*.json", "verdicts/*.json"):
            if list(run.glob(part)) and not list(_mirror(run).glob(part)):
                gaps.append(f"{_mirror(run).relative_to(ROOT)}/{part}")
    for name in (CURATED, "corpus_candidates.csv", "source_format.csv",
                 "gao/record_classification.csv", "gao/paper_dois.csv"):
        if not _mirror(data_path(name)).exists():
            gaps.append(str(_mirror(data_path(name)).relative_to(ROOT)))
    if not (BACKUP / "gold/decisions/adjudicated.json").exists():
        gaps.append("artifacts/backup/gold/decisions/adjudicated.json")
    return gaps


def _mirror(path: Path) -> Path:
    return BACKUP / Path(path).resolve().relative_to(ARTIFACTS)


def main() -> None:
    parser = argparse.ArgumentParser(prog="backup")
    parser.add_argument("--check", action="store_true", help="exit 1 if stale or incomplete")
    parser.add_argument("--restore", action="store_true", help="copy the backup back into place")
    args = parser.parse_args()

    if args.restore:
        for source in sorted(BACKUP.rglob("*")):
            if source.is_file():
                target = ARTIFACTS / source.relative_to(BACKUP)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        print(f"restored {sum(1 for p in BACKUP.rglob('*') if p.is_file()):,} files into "
              f"{ARTIFACTS.relative_to(ROOT)}/")
        return

    if args.check:
        pending = [p for p in wanted()
                   if not (BACKUP / p.relative_to(ARTIFACTS)).exists()
                   or not filecmp.cmp(p, BACKUP / p.relative_to(ARTIFACTS), shallow=False)]
        gaps = missing()
        if pending or gaps:
            for path in pending[:5]:
                print(f"stale: {path.relative_to(ROOT)}")
            for gap in gaps:
                print(f"missing: {gap}")
            print(f"{len(pending)} stale, {len(gaps)} missing; run tools/backup.py")
            raise SystemExit(1)
        print(f"artifacts/backup: current, {len(wanted()):,} files")
        return

    copied, stale = refresh()
    files = [p for p in BACKUP.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    print(f"artifacts/backup: {len(files):,} files, {total / 1e6:.1f} MB "
          f"({copied:,} written, {stale:,} removed)")
    gaps = missing()
    for gap in gaps:
        print(f"  MISSING {gap}")
    print("  every declared input is present" if not gaps else
          f"  {len(gaps)} declared input(s) absent -- the backup cannot rebuild the paper")
    raise SystemExit(1 if gaps else 0)


if __name__ == "__main__":
    main()
