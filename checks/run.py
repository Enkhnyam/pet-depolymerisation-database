"""Run the checks. `run.py` alone runs all of them; pass paths to run a subset.

Scripts are not importable on their own -- they do `from _setup import *`, and this is what
puts checks/ on the path.
"""
import os
import subprocess
import sys
from pathlib import Path

# Every check, found rather than listed. The hand-maintained list this replaces had drifted:
# paper.py and release/release_numbers.py were not in it, so neither ran with the suite, and
# three entries named files that had been deleted. Order is alphabetical by group so a run reads
# the same way twice.
#
# paper.py used to run last. It checked the manuscript -- that every macro the body used was
# defined, and that no literal in the text duplicated a computed value. The manuscript is not in
# this repository, so neither is that check; tools/paper_numbers.py still emits the macros, which
# is the half of the mechanism that is about the evaluation rather than about the prose.
def scripts() -> list[str]:
    here = Path(__file__).parent
    found = sorted(str(p.relative_to(here)) for p in here.glob("*/*.py")
                   if not p.name.startswith("_"))
    return found + ["cost.py", "palette.py"]



if __name__ == "__main__":
    here = Path(__file__).parent
    chosen = sys.argv[1:] or scripts()
    failed = []

    for rel in chosen:
        print(f"\n\033[1m{'─' * 78}\n{rel}\n{'─' * 78}\033[0m")
        # PYTHONPATH is what makes `from _setup import *` resolve; a script run on its own
        # only gets its own directory on the path, not checks/. Output is captured rather than
        # inherited so it stays in order when the whole suite is piped to a file.
        result = subprocess.run([sys.executable, str(here / rel)], cwd=here, text=True,
                                capture_output=True,
                                env={**os.environ, "PYTHONPATH": os.pathsep.join(
                                    [str(here), str((here / rel).parent)])})
        print(result.stdout.rstrip())
        if result.returncode:
            print(result.stderr.rstrip())
            failed.append(rel)

    print(f"\n{'─' * 78}\n{len(chosen) - len(failed)}/{len(chosen)} ran")
    for rel in failed:
        print(f"  FAILED {rel}")
    sys.exit(1 if failed else 0)
