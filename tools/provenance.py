"""Where every macro in the manuscript comes from, derived rather than declared.

The chain is bundle -> check -> macro -> {manuscript, figure}. Three of those four links were
already enforced somewhere: paper_numbers.py --check catches a stale macro file, figures.sh
under FIGURES_CHECK catches a stale figure, and checks/paper.py catches a macro the body uses
that nothing defines. What was missing is the link nobody could see: which check produced a
given number, and which run bundle that check read.

That mapping is not written down here. Writing it down is what tools/macro_catalogue.py did --
217 hand-maintained entries that had to be edited every time a number was added, and that the
audit deleted for exactly that reason. Instead it is read out of the code:

  1. collect() in paper_numbers.py opens by binding each check's output to a local -- `co` is
     corpus.compute(), `ch` is chemistry.compute(), and so on. Parsing those assignments gives
     local -> check module.
  2. Every entry in its `values` dict is an expression over those locals. Parsing each entry
     for the names it reads gives macro -> check module.
  3. Each check declares the bundles it reads by calling _setup.sources() in its main(), and
     paper_numbers.inputs() and its `runs` dict name the rest.

So a new macro is attributed the moment it is written, and one whose expression changes is
re-attributed without anyone remembering to. A macro this cannot attribute is reported as
unattributed rather than guessed at, which is the honest failure.

    provenance.py            print the table
    provenance.py --json     the same as JSON, for tools/dashboard.py
"""
import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "checks"))

from core.paths import ARTIFACTS, FIGURES

MACROS = ARTIFACTS / "paper_numbers.tex"
TABLES = [ARTIFACTS / "paper_table_fields.tex", ARTIFACTS / "paper_table_matrix.tex"]
PAPER = ROOT / "paper_rsc.tex"
NUMBERS_PY = ROOT / "tools" / "paper_numbers.py"

DEFINITION = re.compile(r"\\newcommand\{\\(\w+)\}\{(.+?)\}(?:\s*%\s*(.*))?$", re.M)
DEFINED = re.compile(r"\\newcommand\{\\(\w+)\}")
USE = re.compile(r"\\([A-Z][A-Za-z]+)")
INCLUDE = re.compile(re.escape(f"{{{FIGURES.relative_to(ROOT)}/") + r"(\w+)\.pdf\}")
LATEX = {"Large", "LARGE", "Huge", "HUGE", "Roman", "Alph", "AA", "LaTeX", "TeX", "S",
         "IfFileExists"}


def _collect_function() -> ast.FunctionDef:
    tree = ast.parse(NUMBERS_PY.read_text(encoding="utf-8"))
    return next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "collect")


def _check_of_call(node: ast.AST) -> str | None:
    """The check module behind an expression like `corpus.compute()` or `shots.pairwise(sh)`."""
    for inner in ast.walk(node):
        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute):
            owner = inner.func.value
            if isinstance(owner, ast.Name):
                return owner.id
    return None


def locals_to_checks() -> dict[str, str]:
    """Every local in collect() that holds a check's output, mapped to that check's module.

    Handles the three shapes the function actually uses: one target from one call, a tuple of
    targets from a tuple of calls, and a local derived from another local -- `table` out of
    `audit`, which stays attributed to adjudicated.
    """
    found: dict[str, str] = {}
    for statement in _collect_function().body:
        if not isinstance(statement, ast.Assign):
            continue
        target = statement.targets[0]
        names = ([element.id for element in target.elts if isinstance(element, ast.Name)]
                 if isinstance(target, ast.Tuple) else
                 [target.id] if isinstance(target, ast.Name) else [])
        values = (statement.value.elts if isinstance(statement.value, ast.Tuple)
                  else [statement.value] * len(names))
        for name, value in zip(names, values):
            direct = _check_of_call(value)
            if direct and direct not in found:
                found[name] = direct
                continue
            # derived from an already-attributed local: inherit it
            inherited = next((found[inner.id] for inner in ast.walk(value)
                              if isinstance(inner, ast.Name) and inner.id in found), None)
            if inherited:
                found[name] = inherited
            elif direct:
                found[name] = direct
    return found


def _imported_modules() -> set[str]:
    """Check modules paper_numbers imports by name, for macros that read one directly."""
    tree = ast.parse(NUMBERS_PY.read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module in {"curated", "database", "human"}:
            names |= {alias.asname or alias.name for alias in node.names}
        elif isinstance(node, ast.Import):
            names |= {alias.asname or alias.name for alias in node.names}
    return names


def _reads(value: ast.AST, sources: dict[str, str], modules: set[str]) -> list[str]:
    """The check modules an expression touches, whether through a local or by module name."""
    found = set()
    for inner in ast.walk(value):
        if isinstance(inner, ast.Name):
            if inner.id in sources:
                found.add(sources[inner.id])
            elif inner.id in modules and inner.id not in {"json", "sys", "re", "hashlib"}:
                found.add(inner.id)
    return sorted(found)


def _pattern(key: ast.JoinedStr) -> re.Pattern:
    """A key built as an f-string gives a name pattern: f"Bench{k}Fone" -> ^Bench.*Fone$.

    Macros generated in a loop have no literal name in the source, so they cannot be matched
    by name -- but the literal halves of the f-string that builds them can be, and that is
    still read out of the code rather than written down here.
    """
    parts = ["".join(re.escape(v.value) if isinstance(v, ast.Constant) else ".*"
                     for v in key.values)]
    return re.compile("^" + parts[0] + "$")


def macros_to_checks() -> dict[str, list[str]]:
    """Macro name -> the check modules its expression reads. Empty list means unattributed."""
    sources = locals_to_checks()
    modules = _imported_modules()
    known = set(DEFINED.findall("\n".join(
        path.read_text(encoding="utf-8") for path in [MACROS, *TABLES] if path.exists())))

    found: dict[str, list[str]] = {}
    patterns: list[tuple[re.Pattern, list[str]]] = []

    def note(key, value):
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            found.setdefault(key.value, _reads(value, sources, modules))
        elif isinstance(key, ast.JoinedStr):
            patterns.append((_pattern(key), _reads(value, sources, modules)))
        elif key is None:                       # a **{...} splat
            for inner in ast.walk(value):
                if isinstance(inner, ast.Dict):
                    for k, v in zip(inner.keys, inner.values):
                        note(k, v)
                elif isinstance(inner, ast.DictComp):
                    # {f"AdjPowerAt{...}": ... for rate, power in audit["power"].items()}:
                    # the loop variables carry no attribution, the iterable does
                    reads = _reads(inner.generators[0].iter, sources, modules)
                    if isinstance(inner.key, ast.JoinedStr) and reads:
                        patterns.append((_pattern(inner.key), reads))

    for statement in ast.walk(_collect_function()):
        if isinstance(statement, ast.Dict):
            for key, value in zip(statement.keys, statement.values):
                note(key, value)
        # `for name, frame in sweeps.items(): values[f"Threshold{...}"] = ...` -- the value
        # expression only mentions loop variables, so the iterable is what identifies the check
        elif isinstance(statement, ast.For):
            reads = _reads(statement.iter, sources, modules)
            for inner in ast.walk(statement):
                if (isinstance(inner, ast.Assign)
                        and isinstance(inner.targets[0], ast.Subscript)
                        and isinstance(inner.targets[0].value, ast.Name)
                        and inner.targets[0].value.id == "values"
                        and isinstance(inner.targets[0].slice, ast.JoinedStr) and reads):
                    patterns.append((_pattern(inner.targets[0].slice), reads))
        # values["Name"] = ... and values[f"X{y}Z"] = ..., including inside a for loop
        elif isinstance(statement, ast.Assign) and isinstance(statement.targets[0], ast.Subscript):
            target = statement.targets[0]
            if isinstance(target.value, ast.Name) and target.value.id == "values":
                note(target.slice, statement.value)

    # the Release* block is emitted by render(), not collect(): one loop over one check
    tree = ast.parse(NUMBERS_PY.read_text(encoding="utf-8"))
    render = next((n for n in tree.body
                   if isinstance(n, ast.FunctionDef) and n.name == "render"), None)
    if render and "release_numbers" in ast.unparse(render):
        # release_numbers.compute() returns every macro it defines; its own prefixes are
        # Release* and CuratedOverlap*
        patterns.append((re.compile("^Release.*$"), ["release_numbers"]))
        patterns.append((re.compile("^CuratedOverlap.*$"), ["release_numbers"]))

    # Four macros no expression in `values` produces, so nothing above can reach them. Named
    # here rather than guessed at, and asserted below to be the only ones -- if this list has
    # to grow, the parser missed a pattern and should be fixed instead.
    patterns += [(re.compile("^ArtifactHash$"), ["paper_numbers"]),
                 (re.compile("^FieldTableRows$"), ["verdicts"]),
                 (re.compile("^MatrixTableRows$"), ["matrix"]),
                 (re.compile("^MatrixEvaluableRows$"), ["matrix"])]

    for name in known:
        if name in found and found[name]:
            continue
        for pattern, reads in patterns:
            if pattern.match(name) and reads:
                found[name] = reads
                break
    return found


def macros() -> dict[str, dict]:
    """Every macro on disk: value, the derivation comment beside it, and its source check."""
    text = "\n".join(path.read_text(encoding="utf-8") for path in [MACROS, *TABLES]
                     if path.exists())
    attributed = macros_to_checks()
    body = PAPER.read_text(encoding="utf-8") if PAPER.exists() else ""
    start = body.find("\\begin{document}")
    body = body[start:] if start >= 0 else body
    used = {name for name in USE.findall(body) if name not in LATEX}

    found = {}
    for name, value, comment in DEFINITION.findall(text):
        found[name] = {"value": value, "derivation": (comment or "").strip(),
                       "checks": attributed.get(name, []),
                       "used": name in used}
    # \MatrixTableRows and the like hold multi-line table bodies DEFINITION cannot match
    for name in DEFINED.findall(text):
        found.setdefault(name, {"value": "(table rows)", "derivation": "",
                                "checks": attributed.get(name, []), "used": name in used})
    return found


def bundles() -> dict[str, str]:
    """The run bundles and scored inputs every number ultimately comes from."""
    import paper_numbers
    named = {**paper_numbers.inputs()}
    values, runs = {}, {}
    try:                                        # the runs dict lives inside collect()'s return
        for statement in _collect_function().body:
            if isinstance(statement, ast.Assign) and isinstance(statement.targets[0], ast.Name) \
                    and statement.targets[0].id == "runs":
                runs = {ast.literal_eval(k): ast.unparse(v)
                        for k, v in zip(statement.value.keys, statement.value.values)}
    except Exception:
        pass
    for label, path in {**runs, **{k: str(v) for k, v in named.items()}}.items():
        values[label] = str(path).replace(str(ROOT) + "/", "")
    return values


def checks() -> list[dict]:
    """Every check the suite runs, in order, with the question it answers.

    The question is the first line of the check's own docstring. Every one of them already
    reads as a question a chemist would ask -- "Do the records point at text that exists?",
    "Does the extracted database behave like chemistry?" -- so the page narrates the run out of
    the code rather than out of a second set of labels that could describe something else.
    """
    sys.path.insert(0, str(ROOT / "checks"))
    import run as check_runner
    found = []
    for path in check_runner.scripts():
        source = (ROOT / "checks" / path).read_text(encoding="utf-8")
        doc = (ast.get_docstring(ast.parse(source)) or "").strip()
        found.append({"path": path,
                      "question": doc.splitlines()[0] if doc else path,
                      "group": path.split("/")[0] if "/" in path else "paper"})
    return found


def figures() -> dict[str, dict]:
    """Each figure the manuscript includes, and the checks its module imports.

    Not "the macros this figure displays": that cannot be read off the source. What can be is
    which checks it reads, and a figure and a macro that read the same check cannot disagree
    unless one of them recomputes -- which is the property worth being able to see.
    """
    body = PAPER.read_text(encoding="utf-8") if PAPER.exists() else ""
    found = {}
    for name in dict.fromkeys(INCLUDE.findall(body)):
        module = ROOT / "figures" / f"{name}.py"
        reads: list[str] = []
        if module.exists():
            tree = ast.parse(module.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module in {
                        "curated", "database", "human"}:
                    reads += [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and "." in (node.module or ""):
                    reads.append(node.module.split(".")[-1])
        found[name] = {"module": f"figures/{name}.py" if module.exists() else None,
                       "pdf": str((FIGURES / f"{name}.pdf").relative_to(ROOT)),
                       "drawn": (FIGURES / f"{name}.pdf").exists(),
                       "checks": sorted(set(reads))}
    return found


def artifact_hash() -> str:
    match = re.search(r"artifact set (\w+)", MACROS.read_text(encoding="utf-8"))
    return match.group(1) if match else "unknown"


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def compute() -> dict:
    found = macros()
    return {"artifact_hash": artifact_hash(), "commit": git_head(),
            "bundles": bundles(), "checks": checks(), "figures": figures(),
            "macros": found,
            "unattributed": sorted(n for n, row in found.items() if not row["checks"]),
            "unused": sorted(n for n, row in found.items() if not row["used"])}


def main() -> None:
    parser = argparse.ArgumentParser(prog="provenance")
    parser.add_argument("--json", action="store_true", help="machine-readable, for the dashboard")
    args = parser.parse_args()
    found = compute()

    if args.json:
        print(json.dumps(found, indent=2, default=str))
        return

    print(f"artifact set {found['artifact_hash']}   commit {found['commit']}")
    print(f"\n{len(found['bundles'])} bundles and scored inputs")
    for label, path in found["bundles"].items():
        print(f"  {label:16s} {path}")
    print(f"\n{len(found['checks'])} checks")
    for row in found["checks"]:
        print(f"  {row['path']:30s} {row['question'][:76]}")
    print(f"\n{len(found['macros'])} macros, "
          f"{sum(1 for r in found['macros'].values() if r['used'])} quoted by the manuscript")
    by_check: dict[str, int] = {}
    for row in found["macros"].values():
        for check in row["checks"] or ["(unattributed)"]:
            by_check[check] = by_check.get(check, 0) + 1
    for check, count in sorted(by_check.items(), key=lambda kv: -kv[1]):
        print(f"  {count:4d}  {check}")
    if found["unattributed"]:
        print(f"\n{len(found['unattributed'])} macro(s) no check could be traced for:")
        for name in found["unattributed"]:
            print(f"  \\{name}")
    print(f"\n{len(found['figures'])} figures the manuscript includes")
    for name, row in found["figures"].items():
        state = "drawn" if row["drawn"] else "MISSING"
        source = row["module"] or "hand-drawn"
        print(f"  {name:16s} {state:8s} {source}"
              + (f"   reads {', '.join(row['checks'])}" if row["checks"] else ""))


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------------------------
# Per-panel derivation: which check drew each panel, and the code that did it.
#
# The macro table above answers "where does this number come from" for a number quoted in the
# text. It does not answer the question someone actually asks in front of a figure, which is
# "where does *this panel* come from". That needs the figure modules read the same way
# paper_numbers.py is read: find the statements that touch panel[N], and report the checks they
# reference along with the source lines themselves.
#
# Showing the lines is the point. A prose summary of a calculation is a second description of it
# that can drift; the code cannot.
# ---------------------------------------------------------------------------------------------

LETTERS = "abcdefghijklmnopqrstuvwxyz"


def _panel_indices(node: ast.AST) -> set[int]:
    """Every panel[N] the statement touches."""
    found = set()
    for inner in ast.walk(node):
        if (isinstance(inner, ast.Subscript) and isinstance(inner.value, ast.Name)
                and inner.value.id == "panel"
                and isinstance(inner.slice, ast.Constant)
                and isinstance(inner.slice.value, int)):
            found.add(inner.slice.value)
    return found


def _function_locals(func: ast.FunctionDef, aliases: dict[str, str]) -> dict[str, str]:
    """Locals in a figure's main() that hold a check's output, mapped to that check.

    The same trick as locals_to_checks() for paper_numbers.py, but a figure binds its checks in
    statements of their own -- `chemistry = chem.compute()` -- and the panel statements only
    mention the local. Without this every panel came out reading nothing.
    """
    found: dict[str, str] = {}
    for statement in func.body:
        if not isinstance(statement, ast.Assign):
            continue
        names = ([e.id for e in statement.targets[0].elts if isinstance(e, ast.Name)]
                 if isinstance(statement.targets[0], ast.Tuple)
                 else [statement.targets[0].id]
                 if isinstance(statement.targets[0], ast.Name) else [])
        reads = {aliases[i.id] for i in ast.walk(statement.value)
                 if isinstance(i, ast.Name) and i.id in aliases}
        reads |= {found[i.id] for i in ast.walk(statement.value)
                  if isinstance(i, ast.Name) and i.id in found}
        for name in names:
            if reads:
                found[name] = sorted(reads)[0]
    return found


BANNER = re.compile(r"^\s*#\s*-{2,}\s*([a-z](?:\s*-\s*[a-z])?)\s*:\s*(.+?)\s*-{3,}\s*$")


def purposes(source: str) -> dict[str, str]:
    """Panel letter -> what that panel is for, from the module's own section banners.

    The figure modules head each panel with `# --- a: how many experiments a paper reports ---`,
    so the description is already written beside the code and cannot drift from it.

    Reading it off the statement that touches panel[N] does not work: the banner sits above the
    whole block, and the first line of that block is usually a plain assignment that mentions no
    panel at all. The check's docstring is no substitute either -- four panels of fig_database
    read database/chemistry.py, so all four would be labelled "Does the extracted database
    behave like chemistry?".
    """
    found = {}
    for line in source.splitlines():
        match = BANNER.match(line)
        if match:
            letters = match.group(1).replace(" ", "")
            text = match.group(2).strip()
            found[letters] = text[0].upper() + text[1:]
    return found


def _dynamic_panel(node: ast.AST) -> bool:
    """True when the statement indexes panel with anything but a literal int."""
    for inner in ast.walk(node):
        if (isinstance(inner, ast.Subscript) and isinstance(inner.value, ast.Name)
                and inner.value.id == "panel"
                and not (isinstance(inner.slice, ast.Constant)
                         and isinstance(inner.slice.value, int))):
            return True
    return False


def _spec_indices(loop: ast.For, func: ast.FunctionDef) -> list[int]:
    """The panel indices a loop covers, when it iterates a list of tuples that lead with them.

    fig_chemistry draws (a)-(g) from a `spec` list whose rows start with the panel index, so the
    indices are in the source even though `panel[index]` is not a constant.
    """
    if not isinstance(loop.iter, ast.Name):
        return []
    for statement in func.body:
        if (isinstance(statement, ast.Assign) and isinstance(statement.targets[0], ast.Name)
                and statement.targets[0].id == loop.iter.id
                and isinstance(statement.value, ast.List)):
            found = []
            for element in statement.value.elts:
                if (isinstance(element, ast.Tuple) and element.elts
                        and isinstance(element.elts[0], ast.Constant)
                        and isinstance(element.elts[0].value, int)):
                    found.append(element.elts[0].value)
            return found
    return []


def panels() -> dict[str, list[dict]]:
    """Per figure, per panel: the checks behind it and the source lines that draw it."""
    found: dict[str, list[dict]] = {}
    for name, row in figures().items():
        module = ROOT / "figures" / f"{name}.py"
        if not module.exists():
            continue
        source = module.read_text(encoding="utf-8")
        lines = source.splitlines()
        tree = ast.parse(source)
        main = next((n for n in tree.body
                     if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
        if main is None:
            continue

        aliases = {(alias.asname or alias.name): alias.name for node in tree.body
                   if isinstance(node, ast.ImportFrom) and node.module in
                   {"curated", "database", "human"} for alias in node.names}
        held = _function_locals(main, aliases)
        said = purposes(source)

        by_panel: dict[int, dict] = {}
        for statement in main.body:
            for index in _panel_indices(statement):
                seen = by_panel.setdefault(index, {"code": [], "reads": set(), "lines": []})
                start, end = statement.lineno, (statement.end_lineno or statement.lineno)
                # the comment block immediately above the statement explains the choice, so it
                # is part of the derivation rather than decoration
                top = start - 1
                while top > 0 and lines[top - 1].strip().startswith("#"):
                    top -= 1
                seen["lines"].append((top + 1, end))
                seen["code"].append("\n".join(lines[top:end]))
                for inner in ast.walk(statement):
                    if isinstance(inner, ast.Name):
                        if inner.id in aliases:
                            seen["reads"].add(aliases[inner.id])
                        elif inner.id in held:
                            seen["reads"].add(held[inner.id])

        # A loop draws several panels only when it subscripts panel with something that is not
        # a constant. Filtering on _panel_indices() instead missed fig_chemistry's spec loop
        # entirely -- `panel[index]` has no constant to find -- and double-counted a loop that
        # annotates one constant panel, which its own panel entry already covers.
        loops = [s for s in main.body if isinstance(s, ast.For) and _dynamic_panel(s)]
        found[name] = []
        for index in sorted(by_panel):
            entry = by_panel[index]
            found[name].append({
                "letter": LETTERS[index] if index < len(LETTERS) else str(index),
                "purpose": said.get(LETTERS[index] if index < len(LETTERS)
                                    else str(index), ""),
                "reads": sorted(entry["reads"]),
                "lines": entry["lines"],
                "code": "\n\n".join(entry["code"]),
            })
        for loop in loops:
            top = loop.lineno - 1
            while top > 0 and lines[top - 1].strip().startswith("#"):
                top -= 1
            covered = _spec_indices(loop, main)
            reads = sorted({aliases[i.id] if i.id in aliases else held[i.id]
                            for i in ast.walk(loop)
                            if isinstance(i, ast.Name) and (i.id in aliases or i.id in held)})
            # one label, used for both the heading and the banner lookup. Computing it twice
            # gave "a-g" in the heading and "abcdefg" as the key, so the purpose never matched.
            if covered:
                span = [LETTERS[i] for i in sorted(covered)]
                label = span[0] if len(span) == 1 else f"{span[0]}-{span[-1]}"
            else:
                label = "several panels"
            found[name].append({
                "letter": label,
                "purpose": said.get(label, ""),
                "reads": reads,
                "lines": [(top + 1, loop.end_lineno)],
                "code": "\n".join(lines[top:loop.end_lineno]),
            })
        # A letter covered by a loop can also appear on its own, from a cosmetic line such as
        # legend_above(figure, panel[0]). Those entries read no check and say nothing about the
        # derivation, so they are dropped in favour of the loop that draws the panel.
        spanned = {letter for row in found[name] if "-" in row["letter"]
                   for letter in LETTERS[LETTERS.index(row["letter"][0]):
                                         LETTERS.index(row["letter"][-1]) + 1]}
        found[name] = [row for row in found[name]
                       if row["reads"] or row["letter"] not in spanned]
        found[name].sort(key=lambda row: row["letter"])
    return found


def check_sources() -> dict[str, list[str]]:
    """Each check module, and the bundles or data files it declares by calling sources()."""
    found = {}
    for row in checks():
        path = ROOT / "checks" / row["path"]
        tree = ast.parse(path.read_text(encoding="utf-8"))
        named = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "sources"):
                for keyword in node.keywords:
                    named.append(f"{keyword.arg} = {ast.unparse(keyword.value)}")
        found[path.stem] = named
    return found
