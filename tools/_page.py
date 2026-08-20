"""Shared helpers for the HTML generators.

There is no JavaScript engine on this machine, so a generated page cannot be executed before it
is written. check_script() is the substitute for the one class of error that silently produces a
blank page: a top-level `const` or `let` read before the line declaring it, which throws a
ReferenceError from the temporal dead zone and stops the script dead.

Only column-zero declarations are considered. Anything indented is inside a function or block and
has its own scope, which cannot be resolved without a real parser -- checking those produced
false positives on every block-local named `k` or `w`.
"""
import re

TOP_LEVEL = re.compile(r"^(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=", re.M)


def check_script(js: str) -> list[str]:
    """Top-level names read before they are declared. Empty list means the page will run."""
    lines = js.splitlines()

    declared = {}
    for match in TOP_LEVEL.finditer(js):
        declared.setdefault(match.group(1), js[:match.start()].count("\n"))

    problems = []
    for name, declared_at in sorted(declared.items(), key=lambda item: item[1]):
        word = re.compile(rf"\b{re.escape(name)}\b")
        for number, text in enumerate(lines[:declared_at]):
            stripped = text.lstrip()
            if stripped.startswith("//") or not word.search(text):
                continue
            problems.append(f"{name} is read on line {number + 1} "
                            f"but declared on line {declared_at + 1}")
            break
    return problems


def validate(page: str) -> None:
    """Raise before writing a page whose script cannot run."""
    for script in re.findall(r"<script>(.*?)</script>", page, re.S):
        problems = check_script(script)
        if problems:
            raise SystemExit("refusing to write a broken page:\n  " + "\n  ".join(problems))
