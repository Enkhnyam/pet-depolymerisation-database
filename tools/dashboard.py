"""A local page for verifying the manuscript's numbers, written for whoever has to defend them.

Four steps, in the order someone checking the paper would take them: what the numbers were
computed from, running the checks, what the checks found, and then every number with the check
behind it.

Two rules hold the page honest.

Every number is read off disk when the page is requested. Macro values come from
artifacts/paper_numbers.tex, which of them the manuscript quotes comes from paper_rsc.tex, and
the macro-to-check attribution comes from tools/provenance.py parsing paper_numbers.py. Every
chart series below is a list of *macro names*, never numbers -- so a chart cannot say something
the paper does not, and a macro that disappears leaves a visible gap instead of a stale value.

Every check narrates itself. The line beside each one while it runs is the first line of that
check's own docstring, which in this repo is already the question it answers -- "Do the records
point at text that exists?" -- rather than a second set of labels that could drift from what the
check does.

It serves rather than writing a file because the point is the button: checks/run.py takes a
couple of minutes and the output has to arrive while it runs. A static page cannot start a
process on this machine, and a published one could not at all.

    dashboard.py                 serve on http://127.0.0.1:8000
    dashboard.py --port 9000     somewhere else
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import provenance

# The real commands, not reimplementations of them, so the page cannot pass while the command
# line fails.
JOBS = {
    "checks": {"cmd": ["./.venv/bin/python", "-u", "-W", "ignore", "checks/run.py"],
               "label": "Verify every number",
               "why": "Runs all 24 checks over the run bundles. A couple of minutes."},
    "paper": {"cmd": ["./scripts/paper.sh", "--check"],
              "label": "Is the paper current?",
              "why": "Fails if a macro, a figure or the manuscript has drifted from the checks."},
    "derivation": {"cmd": ["./.venv/bin/python", "-u", "tools/derivation.py"],
                   "label": "Rebuild the derivation report",
                   "why": "Rewrites docs/derivation.md from the figure modules and the checks."},
    "figures": {"cmd": ["./scripts/figures.sh"],
                "label": "Redraw the figures",
                "why": "Redraws each figure from the checks and reports any that had gone stale."},
}

# Every chart's series is a list of macro names. `kind` picks the form the way the dataviz
# form heuristic does: funnel and parts are *ordered*, so they take the single-hue ramp; ranked
# is *nominal*, so every bar is one colour with the largest emphasised -- a ramp on nominal
# categories double-encodes bar length as hue and says nothing the length has not already said.
CHARTS = [
    {"id": "funnel", "kind": "funnel", "unit": "papers",
     "title": "From a Scopus search to extracted papers",
     "note": "Each stage is a subset of the one above. The drop to obtained is licensing, not "
             "relevance."},
    {"id": "verdicts", "kind": "parts", "unit": "records",
     "title": "What the judge said about every extracted record",
     "note": "One verdict per record, so the three sum to the database."},
    {"id": "fields", "kind": "ranked", "unit": "records the judge would change",
     "title": "Which fields the judge rewrote",
     "note": "Masses dominate: a paper states a charge once in the methods, then varies it "
             "implicitly down a table."},
    {"id": "gao", "kind": "parts", "unit": "hand-curated experiments",
     "title": "Why hand curation lists more experiments than we extract",
     "note": "Every one of Gao et al.'s records, each given a single reason by a chemist "
             "reading the paper."},
    {"id": "routes", "kind": "ranked", "unit": "records",
     "title": "Depolymerisation route, read off the solvent",
     "note": "Not extracted but inferred, so a record whose solvent is written unusually lands "
             "in other."},
    {"id": "obtained", "kind": "ranked", "unit": "papers",
     "title": "How the full text reached us",
     "note": "One text-and-data-mining entitlement, which is why the funnel narrows where it "
             "does."},
]

SERIES = {
    "funnel": [("CorpusCandidates", "found by the search"),
               ("CorpusFiltered", "in scope after screening"),
               ("CorpusConverted", "full text obtained"),
               ("DatabasePapers", "read by the extractor")],
    "verdicts": [("JudgeAccepted", "accepted as written"),
                 ("JudgeCorrected", "corrected, with the text cited"),
                 ("JudgeDropped", "rejected outright")],
    "gao": [("GaoShared", "in both datasets"),
            ("GaoChart", "read off a plotted curve"),
            ("GaoSi", "in Supporting Information we lack"),
            ("GaoRule", "a design table outside scope"),
            ("GaoMissed", "in a table we read")],
    "routes": [("RouteGlycolysis", "glycolysis"), ("RouteHydrolysis", "hydrolysis"),
               ("RouteMethanolysis", "methanolysis"), ("RouteOther", "other or unclear")],
    "obtained": [("CorpusElsevierXml", "Elsevier XML"), ("CorpusPdf", "PDF"),
                 ("CorpusEuropePmc", "Europe PMC JATS"),
                 ("CorpusOtherSource", "other source")],
}

# A claim, the two macros that measure it, and what would be wrong if it failed. `invert` means
# the first macro counts violations, so zero is the good answer.
TESTS = [
    {"title": "Yield never exceeds conversion", "hit": "IdentityImpossible",
     "of": "IdentityPairs", "invert": True,
     "why": "An identity rather than a correlation: you cannot recover more monomer than "
            "polymer consumed. A record breaking it is wrong on its face, with no reference "
            "table needed."},
    {"title": "Agreement with hand curation", "hit": "GaoParityAgree", "of": "GaoParityPairs",
     "why": "Matched records -- same paper, same experiment -- agreeing on yield, conversion "
            "and selectivity. The only external reference this work has."},
    {"title": "Citations resolve to real text", "hit": "CitationsResolved",
     "of": "CitationsTotal",
     "why": "Every value carries the identifiers of the chunks it was read from. One that "
            "resolves to nothing cannot be checked against the paper by hand."},
    {"title": "Nothing truncated against the judge's window", "hit": "JudgeOverContext",
     "of": "DatabasePapers", "invert": True,
     "why": "A paper over the window would have been judged on a fragment of itself. The "
            "manuscript claims this in prose; this is the count behind it."},
]

# Headline numbers. A single value is a stat tile, never a one-bar chart.
TILES = [("DatabasePapers", "papers read"), ("DatabaseRecords", "experiments extracted"),
         ("JudgePassRate", "accepted by the judge, %"), ("ReleaseRecords", "records released")]

_job = {"name": None, "output": "", "done": True, "code": None, "checks": {}}
_lock = threading.Lock()


def _narrate(output: str, known: list[str]) -> dict:
    """Which check is running, which have finished, and which failed, read from run.py's output.

    run.py prints each check's path on its own line before it launches it, and lists the
    failures at the end, so the page follows the real run rather than guessing at a schedule.
    """
    seen = [line.strip() for line in output.splitlines() if line.strip() in known]
    failed = {match.group(1) for match in re.finditer(r"FAILED (\S+)", output)}
    finished = bool(re.search(r"\d+/\d+ ran", output))

    state = {}
    for path in known:
        if path in failed:
            state[path] = "failed"
        elif path not in seen:
            state[path] = "pending"
        elif path == seen[-1] and not finished:
            state[path] = "running"             # the last one printed, and the run is not over
        else:
            state[path] = "passed"
    return state


def _run(name: str) -> None:
    job = JOBS[name]
    known = [row["path"] for row in provenance.checks()]
    with _lock:
        _job.update(name=name, output=f"$ {' '.join(job['cmd'])}\n\n", done=False, code=None,
                    checks={path: "pending" for path in known})
    try:
        process = subprocess.Popen(job["cmd"], cwd=ROOT, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, bufsize=1,
                                   env={**os.environ,
                                        "FIGURES_CHECK": "1" if name == "figures" else ""})
        for line in process.stdout:
            with _lock:
                _job["output"] += line
                if name == "checks":
                    _job["checks"] = _narrate(_job["output"], known)
        process.wait()
        with _lock:
            _job.update(done=True, code=process.returncode)
            if name == "checks":
                _job["checks"] = _narrate(_job["output"], known)
    except Exception as error:                   # a missing venv, a bad path: say so on the page
        with _lock:
            _job.update(output=_job["output"] + f"\n{type(error).__name__}: {error}\n",
                        done=True, code=-1)


def payload() -> dict:
    """Everything the page draws, with each chart's numbers resolved from the macro file."""
    state = provenance.compute()
    macros = state["macros"]

    def value(name: str):
        row = macros.get(name)
        if not row:
            return None
        try:
            return float(row["value"].replace(",", "").replace("{,}", "").replace("\\%", ""))
        except ValueError:
            return None

    charts = []
    for spec in CHARTS:
        if spec["id"] == "fields":
            bars = _field_table()
        else:
            bars = [{"macro": macro, "label": label, "value": value(macro)}
                    for macro, label in SERIES[spec["id"]]]
        charts.append({**spec, "bars": [b for b in bars if b["value"] is not None],
                       "missing": [b["macro"] for b in bars if b["value"] is None]})

    tests = []
    for spec in TESTS:
        hit, total = value(spec["hit"]), value(spec["of"])
        if hit is None or not total:
            continue
        good = total - hit if spec.get("invert") else hit
        tests.append({**spec, "hit": hit, "total": total, "share": good / total,
                      "hit_macro": spec["hit"], "of_macro": spec["of"],
                      "shown": f"{int(hit):,} of {int(total):,}"})

    tiles = [{"macro": macro, "label": label,
              "value": macros[macro]["value"] if macro in macros else "—"}
             for macro, label in TILES]
    with _lock:
        job = {"name": _job["name"], "done": _job["done"], "code": _job["code"],
               "checks": dict(_job["checks"])}
    panels = provenance.panels()
    declared = provenance.check_sources()
    questions = {row["path"].split("/")[-1].removesuffix(".py"): row["question"]
                 for row in state["checks"]}
    return {**state, "charts": charts, "tests": tests, "tiles": tiles, "jobs": JOBS,
            "job": job, "panels": panels, "declared": declared, "questions": questions}


def _field_table() -> list[dict]:
    """The judge's field corrections, read out of the generated table macro.

    These are rows rather than macros -- \\FieldTableRows holds the whole table -- so the page
    parses the same file LaTeX reads instead of recomputing the counts.
    """
    path = provenance.ARTIFACTS / "paper_table_fields.tex"
    if not path.exists():
        return []
    bars = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"(.+?) & ([\d,]+) \\\\", line.strip())
        if match:
            label = re.sub(r"\\textdegree\s*", "°", match.group(1))
            label = label.replace("\\%", "%").replace("\\&", "&").strip()
            bars.append({"macro": "FieldTableRows", "label": label,
                         "value": float(match.group(2).replace(",", ""))})
    return bars


STYLE = """
:root{
  --r0:#0A3C34; --r1:#14685C; --r2:#3E9385; --r3:#84BFB4; --r4:#C9E1DC;
  --ink:#12201F; --dim:#5D716E; --faint:#8A9A97; --rule:#DFE7E5; --bg:#F6F8F7;
  --panel:#FFFFFF; --warn:#B4472C; --good:#14685C;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased;
  font:14.5px/1.6 ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}
.wrap{max-width:1120px;margin:0 auto;padding:34px 24px 90px}
a{color:var(--r1)}
h1{font-size:25px;line-height:1.25;margin:0 0 6px;letter-spacing:-.015em;font-weight:640}
.lede{color:var(--dim);font-size:14px;max-width:74ch;margin:0 0 8px}
.meta{color:var(--faint);font-size:12.5px;margin:0 0 30px}
.meta code{background:#EAF1EF;color:var(--r0);padding:1.5px 6px;border-radius:4px;font-size:12px}

.step{margin:0 0 14px;display:flex;align-items:baseline;gap:10px}
.step .no{width:23px;height:23px;border-radius:50%;background:var(--r0);color:#fff;
  font-size:12px;font-weight:700;display:grid;place-items:center;flex:none}
.step h2{font-size:16.5px;margin:0;font-weight:620;letter-spacing:-.01em}
.step p{margin:0;color:var(--dim);font-size:13px}
section{margin-bottom:38px}
.card{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:20px 22px}

/* stat tiles */
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:26px}
.tile{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:15px 17px}
.tile .v{font-size:27px;font-weight:660;letter-spacing:-.02em;color:var(--r0);line-height:1.1}
.tile .l{font-size:12.5px;color:var(--dim);margin-top:3px}
.tile .m{font:10.5px ui-monospace,Menlo,monospace;color:var(--faint);margin-top:7px}

/* the jump bar: five sections and a long table, so the page needs a way back to the top of it */
.jump{position:sticky;top:0;z-index:5;display:flex;gap:2px;justify-content:center;flex-wrap:wrap;
  background:rgba(255,255,255,.93);backdrop-filter:blur(6px);border-bottom:1px solid var(--rule);
  padding:9px 12px}
.jump a{font-size:12.5px;color:var(--dim);text-decoration:none;padding:4px 11px;border-radius:99px}
.jump a:hover{color:var(--ink);background:var(--panel)}
section{scroll-margin-top:52px}

/* the source list */
.srcs{display:grid;grid-template-columns:repeat(2,1fr);gap:0 26px}
.src{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid #F0F4F3;font-size:13px}
.src b{font-weight:600;min-width:118px}
.src span{color:var(--dim);font:11.5px ui-monospace,Menlo,monospace;word-break:break-all}

/* run */
.runbar{display:flex;gap:10px;flex-wrap:wrap;align-items:stretch;margin-bottom:6px}
.run{flex:1;min-width:210px;text-align:left;background:var(--panel);border:1.5px solid var(--rule);
  border-radius:10px;padding:12px 14px;cursor:pointer;font:inherit;color:var(--ink)}
.run:hover:not(:disabled){border-color:var(--r2);background:#FBFDFC}
.run:disabled{opacity:.5;cursor:default}
/* the selected state follows the run, rather than being painted on one button for ever:
   four look-alike buttons with a permanent highlight read as tabs whose selection is stuck */
.run.active{border-color:var(--r0);background:#F1F7F5;box-shadow:inset 0 0 0 1px var(--r0)}
.run.active:disabled{opacity:1}
.run b{display:block;font-size:14px;font-weight:620;margin-bottom:2px}
.run span{font-size:12px;color:var(--dim);line-height:1.45}
.state{margin:16px 0 0;display:flex;align-items:center;gap:9px;font-size:13px}
.pill{display:inline-block;padding:2.5px 10px;border-radius:99px;font-size:11.5px;font-weight:640}
.pill.idle{background:#EEF2F1;color:var(--dim)}
.pill.busy{background:#FFF4DC;color:#7A5A12}
.pill.ok{background:#E4F0EC;color:var(--good)}
.pill.bad{background:#F9E5E0;color:var(--warn)}

/* the narrated checks */
.checks{margin:16px 0 0;border-top:1px solid var(--rule)}
.chk{display:grid;grid-template-columns:18px 1fr auto;gap:11px;align-items:start;
  padding:9px 2px;border-bottom:1px solid #F1F5F4}
.chk .dot{width:9px;height:9px;border-radius:50%;background:var(--rule);margin-top:6px}
.chk.running .dot{background:#E0A33A;animation:pulse 1s infinite}
.chk.passed .dot{background:var(--good)}
.chk.failed .dot{background:var(--warn)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.28}}
.chk q{font-size:13.5px;quotes:none;display:block}
.chk .p{font:11px ui-monospace,Menlo,monospace;color:var(--faint);margin-top:1px}
.chk .s{font-size:11.5px;font-weight:600;color:var(--faint);white-space:nowrap;margin-top:3px}
.chk.passed .s{color:var(--good)} .chk.failed .s{color:var(--warn)}
.chk.running .s{color:#7A5A12}
details{margin-top:14px}
summary{font-size:12.5px;color:var(--dim);cursor:pointer}
.logwrap{margin-top:14px}
.logwrap>b{display:block;font-size:12px;color:var(--dim);font-weight:600}
pre{background:#0B1917;color:#DCE8E4;border-radius:9px;padding:14px 16px;margin:11px 0 0;
  font:11.5px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;max-height:300px;overflow:auto;
  white-space:pre-wrap}

/* claims */
.claims{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
.claim{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:16px 18px}
.claim h3{margin:0 0 3px;font-size:14px;font-weight:620}
.claim .n{font:12.5px ui-monospace,Menlo,monospace;color:var(--r0)}
.claim .why{font-size:12.5px;color:var(--dim);margin:9px 0 0;line-height:1.5}
.meter{height:7px;border-radius:99px;background:#EDF2F1;margin:11px 0 5px;overflow:hidden}
.meter i{display:block;height:100%;background:var(--r1);border-radius:99px}
.claim .macs{font:10.5px ui-monospace,Menlo,monospace;color:var(--faint);margin-top:8px}

/* charts */
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.chart{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:17px 19px}
.chart h3{margin:0 0 2px;font-size:14px;font-weight:620;letter-spacing:-.005em}
.chart .u{font-size:11.5px;color:var(--faint);margin:0 0 12px}
.chart .note{font-size:12px;color:var(--dim);margin:12px 0 0;line-height:1.5}
.chart .gap{font-size:12px;color:var(--warn);margin-top:8px}
svg{display:block;width:100%;height:auto;overflow:visible}
.bl{font:11.5px ui-sans-serif,system-ui;fill:var(--ink)}
.bv{font:11.5px ui-monospace,Menlo,monospace;fill:var(--dim)}
.bar{transition:opacity .12s}
.bar:hover{opacity:.78}
#tip{position:fixed;pointer-events:none;background:var(--ink);color:#fff;font-size:12px;
  padding:6px 9px;border-radius:6px;opacity:0;transition:opacity .1s;z-index:9;white-space:nowrap}
#tip b{font-weight:600}
#tip em{font-style:normal;opacity:.7;font-family:ui-monospace,Menlo,monospace;font-size:11px}

/* panels */
.figname{font-size:13.5px;margin:0 0 12px;font-weight:640;display:flex;align-items:baseline;
  gap:9px}
.figname span{font-size:11.5px;color:var(--faint);font-weight:500}
.panel{display:grid;grid-template-columns:26px 1fr;gap:11px;padding:11px 0;
  border-top:1px solid #F1F5F4}
.panel:first-of-type{border-top:none}
.pl{width:23px;height:23px;border-radius:6px;background:var(--r4);color:var(--r0);
  font-weight:700;font-size:12px;display:grid;place-items:center}
.pq{font-size:13.5px;margin-bottom:2px}
.pm{font-size:11.5px;color:var(--dim)}
.pm code{background:#EEF3F2;padding:1px 5px;border-radius:4px;font-size:11px}
.panel details{margin-top:7px}
.panel summary{font-size:11.5px}
pre.code{background:#0B1917;color:#DCE8E4;font-size:11px;max-height:220px}

/* table */
.tools{display:flex;gap:9px;align-items:center;margin-bottom:13px;flex-wrap:wrap}
input[type=search],select{font:inherit;font-size:13px;padding:8px 11px;border-radius:8px;
  border:1px solid var(--rule);background:var(--panel);color:var(--ink)}
input[type=search]{flex:1;min-width:210px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.055em;
  color:var(--faint);font-weight:650;padding:0 10px 9px;border-bottom:1px solid var(--rule)}
td{padding:8px 10px;border-bottom:1px solid #F2F6F5;vertical-align:top}
tbody tr:hover td{background:#F8FBFA}
.mac{font:12px ui-monospace,Menlo,monospace;color:var(--r0);font-weight:600;white-space:nowrap}
.val{font:12px ui-monospace,Menlo,monospace;white-space:nowrap}
.chkname{font-size:11.5px;color:var(--dim);white-space:nowrap}
.why2{color:var(--dim);font-size:12.5px}
.tag{font-size:10px;padding:1.5px 7px;border-radius:99px;background:#E4F0EC;color:var(--good);
  font-weight:650;white-space:nowrap}
.tag.un{background:#F1F4F3;color:var(--faint)}
.count{color:var(--faint);font-size:12.5px;margin-left:auto}
@media(max-width:820px){.tiles,.grid,.claims,.srcs{grid-template-columns:1fr}}
"""


SCRIPT = r"""
const DATA = window.__DATA__;
const RAMP = ['#0A3C34','#14685C','#3E9385','#84BFB4','#C9E1DC'];
const tip = document.getElementById('tip');
const fmt = n => n.toLocaleString();

function hover(el, label, value, macro, unit){
  el.addEventListener('mousemove', e => {
    tip.innerHTML = '<b>' + fmt(value) + '</b> ' + unit + '<br>' + label +
                    '<br><em>\\' + macro + '</em>';
    tip.style.opacity = 1;
    tip.style.left = Math.min(e.clientX + 13, innerWidth - tip.offsetWidth - 8) + 'px';
    tip.style.top = (e.clientY - tip.offsetHeight - 9) + 'px';
  });
  el.addEventListener('mouseleave', () => tip.style.opacity = 0);
}

/* Horizontal bars. Ordered data (funnel, parts) takes the ramp; nominal data gets one colour
   with the largest emphasised, because a ramp on nominal categories re-encodes bar length. */
function bars(host, chart){
  const rows = chart.bars, n = rows.length;
  if (!n) { host.innerHTML = '<p class="gap">no data</p>'; return; }
  const ranked = chart.kind === 'ranked';
  const order = ranked ? [...rows].sort((a,b) => b.value - a.value) : rows;
  const top = Math.max(...order.map(r => r.value));
  const H = 30, PAD = 4, W = 560;
  // the gutter follows the longest label; a fixed one ran the Supporting
  // Information label off the left edge of its panel
  const LW = Math.max(96, Math.min(232,
      8 + Math.max(...order.map(r => r.label.length)) * 6.1));
  const svg = ['<svg viewBox="0 0 ' + W + ' ' + (n*H + PAD) + '" role="img">'];
  order.forEach((r, i) => {
    const y = i*H + PAD, w = Math.max(2, (r.value/top) * (W - LW - 62));
    const colour = ranked ? (i === 0 ? RAMP[0] : RAMP[1])
                          : RAMP[Math.min(i, RAMP.length - 1)];
    svg.push(
      '<text class="bl" x="' + (LW-9) + '" y="' + (y+13) + '" text-anchor="end">' +
        r.label + '</text>' +
      '<rect class="bar" data-i="' + i + '" x="' + LW + '" y="' + (y+3) + '" width="' + w +
        '" height="15" rx="4" fill="' + colour + '"></rect>' +
      '<text class="bv" x="' + (LW+w+7) + '" y="' + (y+15) + '">' + fmt(r.value) + '</text>');
  });
  svg.push('</svg>');
  host.innerHTML = svg.join('');
  host.querySelectorAll('rect.bar').forEach(rect => {
    const r = order[+rect.dataset.i];
    hover(rect, r.label, r.value, r.macro, chart.unit || '');
  });
}

DATA.charts.forEach(chart => {
  const host = document.getElementById('c-' + chart.id);
  if (host) bars(host, chart);
});

/* --- the narrated run ----------------------------------------------------------------- */
/* Three faults were reported here and all three were real. Only the check run showed any
   progress, so the other three buttons looked like dead tabs; the highlight sat permanently on
   the first button whatever you pressed, so the selection looked stuck; and every start() added
   another poller without stopping the last, so a second run updated the page twice a tick. */
let timer = null;
const pill = document.getElementById('pill'), log = document.getElementById('log'),
      logwrap = document.getElementById('logwrap'), hint = document.getElementById('hint'),
      list = document.getElementById('checklist');

function select(name){
  document.querySelectorAll('.run').forEach(
    b => b.classList.toggle('active', b.dataset.job === name));
  const narrated = name === 'checks';
  list.hidden = !narrated;              /* only the check run has per-check narration ... */
  hint.hidden = !narrated;
  logwrap.hidden = false;               /* ... but every run shows its output as it arrives */
}

async function start(name){
  clearInterval(timer);
  select(name);
  document.querySelectorAll('.run').forEach(b => b.disabled = true);
  document.querySelectorAll('.chk').forEach(row => {      /* clear the last run's verdicts */
    row.className = 'chk pending';
    row.querySelector('.s').textContent = '';
  });
  log.textContent = 'starting…';
  pill.className = 'pill busy'; pill.textContent = DATA.jobs[name] + ' — running';
  await fetch('/api/run/' + name, {method:'POST'});
  timer = setInterval(poll, 600); poll();
}

async function poll(){
  const s = await (await fetch('/api/job')).json();
  log.textContent = s.output || '(waiting)';
  log.scrollTop = log.scrollHeight;
  for (const [path, value] of Object.entries(s.checks || {})){
    const row = document.querySelector('[data-check="' + path + '"]');
    if (!row) continue;
    row.className = 'chk ' + value;
    row.querySelector('.s').textContent =
      value === 'pending' ? '' : value === 'running' ? 'checking…' : value;
  }
  if (s.done){
    clearInterval(timer); timer = null;
    document.querySelectorAll('.run').forEach(b => b.disabled = false);
    pill.className = 'pill ' + (s.code === 0 ? 'ok' : 'bad');
    const what = DATA.jobs[s.name] || s.name;
    pill.textContent = s.code === 0 ? what + ' — passed'
                                    : what + ' — failed, exit ' + s.code;
  }
}

document.querySelectorAll('.run').forEach(
  b => b.addEventListener('click', () => start(b.dataset.job)));

/* a reload while a run is in flight picks it back up rather than showing "not run yet" */
if (DATA.job && DATA.job.name){
  select(DATA.job.name);
  if (!DATA.job.done){
    document.querySelectorAll('.run').forEach(b => b.disabled = true);
    pill.className = 'pill busy';
    pill.textContent = (DATA.jobs[DATA.job.name] || DATA.job.name) + ' — running';
    timer = setInterval(poll, 600);
  }
  poll();
}

/* --- the table ------------------------------------------------------------------------ */
const rows = [...document.querySelectorAll('#macros tbody tr')];
const q = document.getElementById('q'), pick = document.getElementById('pick'),
      only = document.getElementById('only'), count = document.getElementById('count');
function filter(){
  const text = q.value.trim().toLowerCase(), check = pick.value, quoted = only.checked;
  let shown = 0;
  for (const row of rows){
    const hit = (!text || row.dataset.search.includes(text))
             && (!check || row.dataset.check.split(' ').includes(check))
             && (!quoted || row.dataset.used === '1');
    row.style.display = hit ? '' : 'none';
    shown += hit ? 1 : 0;
  }
  count.textContent = shown + ' of ' + rows.length + ' shown';
}
[q, pick].forEach(el => el.addEventListener('input', filter));
only.addEventListener('change', filter);
filter();
"""


def esc(text) -> str:
    import html as _html
    return _html.escape(str(text), quote=True)


def render(state: dict) -> str:
    macros, checks = state["macros"], state["checks"]
    quoted = sum(1 for row in macros.values() if row["used"])
    spare = len(macros) - quoted

    tiles = "".join(
        f'<div class="tile"><div class="v">{esc(t["value"])}</div>'
        f'<div class="l">{esc(t["label"])}</div>'
        f'<div class="m">\\{esc(t["macro"])}</div></div>' for t in state["tiles"])

    sources = "".join(f'<div class="src"><b>{esc(label)}</b><span>{esc(path)}</span></div>'
                      for label, path in state["bundles"].items())

    running = state["job"].get("name")
    buttons = "".join(
        f'<button class="run{" active" if name == running else ""}" data-job="{name}">'
        f'<b>{esc(job["label"])}</b><span>{esc(job["why"])}</span></button>'
        for name, job in JOBS.items())
    # nothing has run yet in this process: no button is selected and no output pane is shown,
    # rather than a highlight on a button that was never pressed
    hidden_hint = "" if running in (None, "checks") else " hidden"
    hidden_list = "" if running in (None, "checks") else " hidden"
    hidden_log = "" if running else " hidden"

    checklist = "".join(
        f'<div class="chk pending" data-check="{esc(row["path"])}"><div class="dot"></div>'
        f'<div><q>{esc(row["question"])}</q><div class="p">{esc(row["path"])}</div></div>'
        f'<div class="s"></div></div>' for row in checks)

    claims = "".join(
        f'<div class="claim"><h3>{esc(t["title"])}</h3>'
        f'<div class="n">{esc(t["shown"])}'
        f'{" break it" if t.get("invert") else " agree"} &middot; '
        f'{t["share"] * 100:.1f}% clean</div>'
        f'<div class="meter"><i style="width:{max(1.0, t["share"] * 100):.1f}%"></i></div>'
        f'<p class="why">{esc(t["why"])}</p>'
        f'<div class="macs">\\{esc(t["hit_macro"])} of \\{esc(t["of_macro"])}</div></div>'
        for t in state["tests"])

    charts = "".join(
        f'<div class="chart"><h3>{esc(c["title"])}</h3>'
        f'<p class="u">{esc(c["unit"])}</p><div id="c-{c["id"]}"></div>'
        f'<p class="note">{esc(c["note"])}</p>'
        + (f'<p class="gap">missing macros: {esc(", ".join(c["missing"]))}</p>'
           if c["missing"] else "")
        + '</div>' for c in state["charts"])

    by_check: dict[str, int] = {}
    for row in macros.values():
        for check in row["checks"]:
            by_check[check] = by_check.get(check, 0) + 1
    options = "".join(f'<option value="{esc(c)}">{esc(c)} ({n})</option>'
                      for c, n in sorted(by_check.items()))

    body = []
    for name, row in sorted(macros.items()):
        joined = " ".join(row["checks"])
        search = f'{name} {row["value"]} {row["derivation"]} {joined}'.lower()
        tag = ('<span class="tag">in the paper</span>' if row["used"]
               else '<span class="tag un">not quoted</span>')
        body.append(
            f'<tr data-search="{esc(search)}" data-check="{esc(joined)}"'
            f' data-used="{1 if row["used"] else 0}">'
            f'<td class="mac">\\{esc(name)}</td><td class="val">{esc(row["value"])}</td>'
            f'<td class="chkname">{esc(joined or "—")}</td><td>{tag}</td>'
            f'<td class="why2">{esc(row["derivation"])}</td></tr>')

    panelblocks = []
    for figure, rows in state["panels"].items():
        cards = []
        for row in rows:
            reads = ", ".join(row["reads"]) or "—"
            asks = " ".join(state["questions"].get(name, "") for name in row["reads"]).strip()
            purpose = row.get("purpose") or asks
            inputs = "; ".join(sorted({item for name in row["reads"]
                                       for item in state["declared"].get(name, [])})) or "—"
            cards.append(
                f'<div class="panel"><div class="pl">{esc(row["letter"])}</div>'
                f'<div class="pb"><div class="pq">{esc(purpose) or "&mdash;"}</div>'
                f'<div class="pm">by <code>{esc(reads)}</code>, which asks '
                f'&ldquo;{esc(asks)}&rdquo;</div>'
                f'<div class="pm">reading <code>{esc(inputs)}</code></div>'
                f'<details><summary>the code that draws it</summary>'
                f'<pre class="code">{esc(row["code"])}</pre></details></div></div>')
        panelblocks.append(
            f'<div class="card"><h3 class="figname">{esc(figure)}'
            f'<span>{len(rows)} panels</span></h3>{"".join(cards)}</div>')
    panelblocks = "".join(panelblocks)

    figures = " &middot; ".join(
        f'{esc(n)} <b>{"drawn" if r["drawn"] else "MISSING"}</b>'
        for n, r in state["figures"].items())

    untraced = state["unattributed"]
    alarm = ("" if not untraced else
             f'<p class="lede" style="color:var(--warn)"><b>{len(untraced)} macro(s) no check '
             f'can be traced for:</b> {esc(", ".join(untraced))}</p>')

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Verifying the PET depolymerisation database</title>
<style>{STYLE}</style></head><body>
<div id="tip"></div>
<nav class="jump"><a href="#panels">figures</a><a href="#inputs">inputs</a>
  <a href="#run">run the checks</a><a href="#found">findings</a>
  <a href="#numbers">the numbers</a></nav>
<div class="wrap">
  <h1>Every number in the paper, and the evidence behind it</h1>
  <p class="lede">Nothing here is typed in. Each figure below reads its numbers from the same
    macro file the manuscript does, so this page and the paper cannot disagree &mdash; and each
    check states the question it answers as it runs.</p>
  <p class="meta">artifact set <code>{esc(state['artifact_hash'])}</code> &middot;
    commit <code>{esc(state['commit'])}</code> &middot;
    {len(macros)} macros, {quoted} quoted by the manuscript &middot; figures: {figures}</p>
  {alarm}

  <div class="tiles">{tiles}</div>

  <section id="panels">
    <div class="step"><div class="no">1</div><div>
      <h2>Pick a panel, see how it was computed</h2>
      <p>Every panel of every figure, the check behind it, what that check reads, and the code
        that draws it.</p></div></div>
    {panelblocks}
  </section>

  <section id="inputs">
    <div class="step"><div class="no">2</div><div>
      <h2>What the numbers were computed from</h2>
      <p>Seven inputs. Change any one and the artifact set above changes with it.</p></div></div>
    <div class="card"><div class="srcs">{sources}</div></div>
  </section>

  <section id="run">
    <div class="step"><div class="no">3</div><div>
      <h2>Check it yourself</h2>
      <p>These run the same commands as the terminal, on this machine, now.</p></div></div>
    <div class="card">
      <div class="runbar">{buttons}</div>
      <div class="state"><span id="pill" class="pill idle">not run yet</span>
        <span id="hint" style="color:var(--dim);font-size:12.5px"{hidden_hint}>each check below
          says what it is asking</span></div>
      <div class="checks" id="checklist"{hidden_list}>{checklist}</div>
      <div class="logwrap" id="logwrap"{hidden_log}><b>output</b>
        <pre id="log">nothing yet</pre></div>
    </div>
  </section>

  <section id="found">
    <div class="step"><div class="no">4</div><div>
      <h2>What the checks found</h2>
      <p>Four claims a referee asks first, then the shape of the data behind them.</p></div></div>
    <div class="claims">{claims}</div>
    <div class="grid" style="margin-top:14px">{charts}</div>
  </section>

  <section id="numbers">
    <div class="step"><div class="no">5</div><div>
      <h2>The numbers the manuscript quotes</h2>
      <p>The {quoted} macros that reach the paper, each with the check that produced it. The
        other {spare} are computed and checked too &mdash; they are available rather than dead
        &mdash; but they are off by default, because a table of numbers nothing cites is a
        table nobody can use.</p></div></div>
    <div class="card">
      <div class="tools">
        <input type="search" id="q" placeholder="search a macro, a value or a description">
        <select id="pick"><option value="">every check</option>{options}</select>
        <label style="font-size:12.5px;color:var(--dim)">
          <input type="checkbox" id="only" checked> only what the paper quotes</label>
        <span class="count" id="count"></span>
      </div>
      <table id="macros"><thead><tr><th>macro</th><th>value</th><th>from</th><th></th>
        <th>what it means</th></tr></thead><tbody>{''.join(body)}</tbody></table>
    </div>
  </section>
</div>
<script>window.__DATA__ = {json.dumps({"charts": state["charts"], "job": state["job"],
                                        "jobs": {n: j["label"] for n, j in JOBS.items()}},
                                       default=str)};</script>
<script>{SCRIPT}</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, kind: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.startswith("/api/job"):
            with _lock:
                self._send(json.dumps(_job).encode(), "application/json")
        elif self.path.startswith("/api/state"):
            self._send(json.dumps(payload(), default=str).encode(), "application/json")
        else:
            self._send(render(payload()).encode(), "text/html; charset=utf-8")

    def do_POST(self) -> None:
        name = self.path.rsplit("/", 1)[-1]
        if name in JOBS and _job["done"]:
            threading.Thread(target=_run, args=(name,), daemon=True).start()
        self._send(b"{}", "application/json")

    def log_message(self, *_):                   # the page is the log
        pass


def main() -> None:
    parser = argparse.ArgumentParser(prog="dashboard")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-open", action="store_true", help="do not open a browser")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    where = f"http://127.0.0.1:{args.port}"
    print(f"serving {where}   (ctrl-c to stop)")
    if not args.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(where)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
