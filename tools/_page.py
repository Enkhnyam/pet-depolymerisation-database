"""Shared helpers for the HTML generators.

There is no JavaScript engine on this machine -- no node, no deno -- so a generated page cannot
be executed before it is written. check_script() is the substitute for the one class of error
that silently produces a blank page: a top-level `const` or `let` read before the line declaring
it, which throws a ReferenceError from the temporal dead zone and stops the script dead.

An audit proposed replacing this with `node --check`. Two reasons that does not work: node is
not installed here, and `--check` is a parse, not a scope analysis, so it would not catch a
temporal-dead-zone read even if it were. 43 lines guarding a blank page in a document a chemist
is asked to work through stays.

Only column-zero lines are considered, for declarations and for reads alike. Anything indented is
inside a function or block with its own scope, which cannot be resolved without a real parser --
looking at those produced false positives on every block-local named `k` or `w`.

    _page.py    run the self-check
"""
import re

TOP_LEVEL = re.compile(r"^(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=", re.M)

# These pages inject their Python-side data through SCREAMING_CASE constants -- DATA, LABELS,
# ANSWERS -- and a generator that adds one to the template without adding the matching
# `const NAME = __NAME__;` produces a page that throws ReferenceError on first render and shows
# a chemist a blank right-hand pane. That happened: review_corrections.py grew a SEVERITY
# constant, used it in a card, and never declared it. The TDZ check could not see it, because
# the name was not declared late -- it was not declared at all.
DECLARED = re.compile(r"\b(?:const|let|var|function|class)\s+([A-Z][A-Z0-9_$]*)\b")
USED = re.compile(r"(?<![.\w$])([A-Z][A-Z0-9_$]{2,})(?![\w$])")

# Screaming-case names the browser itself provides, which are used and never declared.
BUILT_IN = {"JSON", "URL", "NaN", "Infinity", "Math", "Object", "Array", "Number", "String",
            "Set", "Map", "Date", "RegExp", "Blob", "Event", "Node", "Element", "Promise",
            "NodeFilter", "SHOW_TEXT", "XMLHttpRequest", "FileReader", "TEXT"}


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
            # Reads are judged at column zero, for the same reason declarations are: an indented
            # line is inside a block with its own scope. Matching reads anywhere flagged
            # `function f() { const k = 1; ... }` on an earlier line as a read of a later
            # top-level `k` -- found by the self-check below the moment it was written.
            if text[:1].isspace() or not text.strip() or text.lstrip().startswith("//"):
                continue
            if not word.search(text):
                continue
            # A line that declares this name itself is not a read of the later one. Catches the
            # one-liner `function f() { const k = 1; return k; }` sitting above a top-level `k`.
            if re.search(rf"\b(?:const|let|var|function)\s+{re.escape(name)}\b", text):
                continue
            problems.append(f"{name} is read on line {number + 1} "
                            f"but declared on line {declared_at + 1}")
            break

    # Undeclared injected constants. Comments and string literals come out first, because
    # neither is a read: the prose above a function names the constants it is about, and
    # 'LABEL', 'SELECT' and "PET g" are data. Leaving them in flagged all three.
    code = re.sub(r"//[^\n]*", "", js)
    for quote in ("'", '"', "`"):
        code = re.sub(rf"{quote}(?:\\.|[^{quote}\\])*{quote}", '""', code, flags=re.S)
    known = set(DECLARED.findall(code)) | BUILT_IN
    for name in sorted(set(USED.findall(code)) - known):
        problems.append(f"{name} is used but never declared -- the page will throw "
                        f"ReferenceError on first render")
    return problems


def validate(page: str) -> None:
    """Raise before writing a page whose script cannot run."""
    for script in re.findall(r"<script>(.*?)</script>", page, re.S):
        problems = check_script(script)
        if problems:
            raise SystemExit("refusing to write a broken page:\n  " + "\n  ".join(problems))


if __name__ == "__main__":
    assert check_script("const rows = DATA;\nconst DATA = [];") == \
        ["DATA is read on line 1 but declared on line 2"]
    assert check_script("const DATA = [];\nconst rows = DATA;") == []
    assert check_script("// DATA is fine here\nconst DATA = [];") == []
    assert check_script("function f() { const k = 1; return k; }\nconst k = 2;") == []
    # the SEVERITY bug, in miniature
    assert check_script("const rows = SEVERITY.map(x => x);") == \
        ["SEVERITY is used but never declared -- the page will throw ReferenceError "
         "on first render"]
    assert check_script("const SEVERITY = [];\nconst rows = SEVERITY.map(x => x);") == []
    assert check_script("// SEVERITY is described here\nconst a = 1;") == []
    assert check_script("const a = JSON.parse('[]');\nconst b = Math.max(1, 2);") == []
    # names that only ever appear inside string literals are data, not identifiers
    assert check_script("const t = ['BUTTON', 'INPUT'].includes(x) ? \"PET g\" : `SELECT`;") == []
    # a property access is not a use of a binding of the same name
    assert check_script("const SEV = 1;\nel.dataset.SEV;") == []
    try:
        validate("<script>const a = B;\nconst B = 1;</script>")
    except SystemExit as exit:
        assert "B is read on line 1" in str(exit)
    else:
        raise AssertionError("validate() let a broken page through")
    print("_page self-check ok")
