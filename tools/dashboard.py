"""A local page for the chain: bundle -> check -> macro -> manuscript and figures.

Every number on it is read off disk at the moment the page is requested -- the macro values come
from artifacts/paper_numbers.tex, which macros the manuscript quotes comes from paper_rsc.tex,
and the attribution comes from tools/provenance.py parsing paper_numbers.py. Nothing is
duplicated here, so the page cannot disagree with the paper; if it is wrong, the file it read is
wrong.

It serves rather than writes a file because the point is the buttons: checks/run.py takes a
couple of minutes and the output has to arrive while it runs. A static page cannot start a
process on this machine, and a published one certainly cannot.

    dashboard.py                 serve on http://127.0.0.1:8000
    dashboard.py --port 9000     somewhere else
"""
import argparse
import html
import json
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

# What the buttons run. Each is the real command, not a reimplementation of it, so the page
# cannot pass while the command line fails.
JOBS = {
    "checks": (["./.venv/bin/python", "-W", "ignore", "checks/run.py"],
               "every check, over the run bundles"),
    "paper": (["./scripts/paper.sh", "--check"],
              "macros, figures and manuscript all current"),
    "figures": (["./scripts/figures.sh"],
                "redraw from the checks"),
}

_job = {"name": None, "output": "", "done": True, "code": None}
_lock = threading.Lock()


def _run(name: str) -> None:
    command, _ = JOBS[name]
    with _lock:
        _job.update(name=name, output=f"$ {' '.join(command)}\n\n", done=False, code=None)
    try:
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, bufsize=1,
                                   env={**__import__("os").environ,
                                        "FIGURES_CHECK": "1" if name == "figures" else ""})
        for line in process.stdout:
            with _lock:
                _job["output"] += line
        process.wait()
        with _lock:
            _job.update(done=True, code=process.returncode)
    except Exception as error:                  # a missing venv, a bad path: say so on the page
        with _lock:
            _job.update(output=_job["output"] + f"\n{type(error).__name__}: {error}\n",
                        done=True, code=-1)


STYLE = """
:root{
  --r0:#0A3C34; --r1:#14685C; --r2:#3E9385; --r3:#84BFB4; --r4:#C9E1DC;
  --ink:#12201F; --dim:#5D716E; --rule:#D2DEDB; --bg:#F7F8F7; --panel:#FFFFFF;
  --warn:#B4472C;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 24px 80px}
h1{font-size:20px;margin:0 0 4px;letter-spacing:-.01em}
.sub{color:var(--dim);font-size:13px;margin:0 0 24px}
.sub code{background:var(--r4);padding:1px 6px;border-radius:4px;font-size:12px}
.card{background:var(--panel);border:1px solid var(--rule);border-radius:10px;padding:18px 20px;
  margin-bottom:20px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.07em;color:var(--dim);
  margin:0 0 14px;font-weight:600}

/* --- the flow ------------------------------------------------------------------------- */
.flow{display:grid;grid-template-columns:1fr 22px 1fr 22px 1fr 22px 1fr;align-items:stretch;
  gap:0}
.stage{background:var(--panel);border:1.5px solid var(--r3);border-radius:9px;padding:13px 14px}
.stage.lead{border-color:var(--r0);background:#F2F8F6}
.stage .n{font-size:26px;font-weight:650;line-height:1.1;color:var(--r0)}
.stage .t{font-size:12px;color:var(--dim);margin-top:2px}
.stage ul{margin:9px 0 0;padding:0;list-style:none;font-size:11px;color:var(--dim);
  max-height:132px;overflow:auto}
.stage li{padding:1.5px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.arrow{display:flex;align-items:center;justify-content:center;color:var(--r2);font-size:17px}

/* --- run panel ------------------------------------------------------------------------ */
.runs{display:flex;gap:9px;flex-wrap:wrap;align-items:center}
button{font:inherit;font-size:13px;font-weight:550;padding:8px 15px;border-radius:7px;
  border:1.5px solid var(--r1);background:var(--r1);color:#fff;cursor:pointer}
button.ghost{background:var(--panel);color:var(--r0)}
button:disabled{opacity:.45;cursor:default}
button:hover:not(:disabled){filter:brightness(1.08)}
.hint{color:var(--dim);font-size:12px}
pre{background:#0C1A18;color:#D9E6E2;border-radius:8px;padding:14px 16px;margin:14px 0 0;
  font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;max-height:340px;overflow:auto;
  white-space:pre-wrap}
.pill{display:inline-block;padding:2px 9px;border-radius:99px;font-size:11px;font-weight:600}
.ok{background:#E3F0EC;color:var(--r0)} .bad{background:#F7E4DF;color:var(--warn)}
.run{background:#FFF3D8;color:#7A5A12}

/* --- table ---------------------------------------------------------------------------- */
.tools{display:flex;gap:9px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
input[type=search],select{font:inherit;font-size:13px;padding:7px 11px;border-radius:7px;
  border:1px solid var(--rule);background:var(--panel);color:var(--ink)}
input[type=search]{flex:1;min-width:200px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--dim);
  font-weight:600;padding:0 10px 8px;border-bottom:1px solid var(--rule)}
td{padding:7px 10px;border-bottom:1px solid #EFF3F2;vertical-align:top}
tr:hover td{background:#F6FAF9}
.mac{font:12px ui-monospace,Menlo,monospace;color:var(--r0);font-weight:600;white-space:nowrap}
.val{font:12px ui-monospace,Menlo,monospace;white-space:nowrap}
.chk{font-size:11px;color:var(--dim);white-space:nowrap}
.why{color:var(--dim);font-size:12px}
.tag{font-size:10px;padding:1px 7px;border-radius:99px;background:var(--r4);color:var(--r0);
  font-weight:600}
.tag.un{background:#EFF3F2;color:var(--dim)}
.count{color:var(--dim);font-size:12px;margin-left:auto}
"""

SCRIPT = """
const rows = [...document.querySelectorAll('#macros tbody tr')];
const q = document.getElementById('q'), pick = document.getElementById('pick'),
      only = document.getElementById('only'), count = document.getElementById('count');
function filter(){
  const text = q.value.toLowerCase(), check = pick.value, used = only.checked;
  let shown = 0;
  for (const row of rows){
    const hit = (!text || row.dataset.search.includes(text))
             && (!check || row.dataset.check.split(' ').includes(check))
             && (!used || row.dataset.used === '1');
    row.hidden = !hit; shown += hit ? 1 : 0;
  }
  count.textContent = shown + ' of ' + rows.length;
}
[q, pick].forEach(el => el.addEventListener('input', filter));
only.addEventListener('change', filter);
filter();

let polling = null;
async function start(name){
  document.querySelectorAll('button[data-job]').forEach(b => b.disabled = true);
  document.getElementById('status').className = 'pill run';
  document.getElementById('status').textContent = 'running';
  await fetch('/api/run/' + name, {method: 'POST'});
  polling = setInterval(poll, 700); poll();
}
async function poll(){
  const state = await (await fetch('/api/job')).json();
  const log = document.getElementById('log');
  log.textContent = state.output || '(no output yet)';
  log.scrollTop = log.scrollHeight;
  if (state.done){
    clearInterval(polling);
    document.querySelectorAll('button[data-job]').forEach(b => b.disabled = false);
    const pill = document.getElementById('status');
    pill.className = 'pill ' + (state.code === 0 ? 'ok' : 'bad');
    pill.textContent = state.code === 0 ? 'passed' : 'failed (exit ' + state.code + ')';
  }
}
document.querySelectorAll('button[data-job]').forEach(
  b => b.addEventListener('click', () => start(b.dataset.job)));
"""


def render(state: dict) -> str:
    macros = state["macros"]
    used = sum(1 for row in macros.values() if row["used"])
    by_check: dict[str, int] = {}
    for row in macros.values():
        for check in row["checks"] or ["(none)"]:
            by_check[check] = by_check.get(check, 0) + 1

    def li(items):
        return "".join(f"<li>{html.escape(str(x))}</li>" for x in items)

    figures = state["figures"]
    drawn = sum(1 for row in figures.values() if row["drawn"])

    stages = f"""
    <div class="stage lead"><div class="n">{len(state['bundles'])}</div>
      <div class="t">run bundles and scored inputs</div>
      <ul>{li(state['bundles'].values())}</ul></div>
    <div class="arrow">&rarr;</div>
    <div class="stage"><div class="n">{len(state['checks'])}</div>
      <div class="t">checks, each naming what it read</div>
      <ul>{li(state['checks'])}</ul></div>
    <div class="arrow">&rarr;</div>
    <div class="stage"><div class="n">{len(macros)}</div>
      <div class="t">macros, {used} quoted by the manuscript</div>
      <ul>{li(f"{count} from {name}" for name, count in
              sorted(by_check.items(), key=lambda kv: -kv[1]))}</ul></div>
    <div class="arrow">&rarr;</div>
    <div class="stage lead"><div class="n">{drawn}<span style="font-size:15px">/{len(figures)}</span></div>
      <div class="t">figures drawn, and one manuscript</div>
      <ul>{li(f"{name}: {'drawn' if row['drawn'] else 'MISSING'}"
              for name, row in figures.items())}</ul></div>
    """

    buttons = "".join(
        f'<button data-job="{name}" class="{"" if name == "checks" else "ghost"}">'
        f'{"Run " + name}</button>' for name in JOBS)
    hints = " &middot; ".join(f"<b>{name}</b> {why}" for name, (_, why) in JOBS.items())

    body = []
    for name, row in sorted(macros.items()):
        checks = " ".join(row["checks"])
        body.append(
            f'<tr data-search="{html.escape((name + " " + row["value"] + " " + row["derivation"] + " " + checks).lower())}"'
            f' data-check="{html.escape(checks)}" data-used="{1 if row["used"] else 0}">'
            f'<td class="mac">\\{html.escape(name)}</td>'
            f'<td class="val">{html.escape(row["value"])}</td>'
            f'<td class="chk">{html.escape(checks or "—")}</td>'
            f'<td>{"<span class=tag>quoted</span>" if row["used"] else "<span class=\'tag un\'>unused</span>"}</td>'
            f'<td class="why">{html.escape(row["derivation"])}</td></tr>')

    options = "".join(f'<option value="{html.escape(c)}">{html.escape(c)}</option>'
                      for c in sorted(by_check) if c != "(none)")

    unattributed = state["unattributed"]
    warning = ("" if not unattributed else
               f'<p class="sub" style="color:var(--warn)"><b>{len(unattributed)} macro(s) '
               f'no check could be traced for:</b> {html.escape(", ".join(unattributed))}</p>')

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>PET depolymerisation — number provenance</title><style>{STYLE}</style></head><body>
<div class="wrap">
  <h1>Where every number in the manuscript comes from</h1>
  <p class="sub">artifact set <code>{state['artifact_hash']}</code> &middot; commit
    <code>{state['commit']}</code> &middot; read from
    <code>artifacts/paper_numbers.tex</code> and <code>paper_rsc.tex</code> on this request, so
    this page cannot disagree with the paper.</p>
  {warning}

  <div class="card"><h2>The chain</h2><div class="flow">{stages}</div></div>

  <div class="card"><h2>Run it</h2>
    <div class="runs">{buttons}<span id="status" class="pill ok">idle</span></div>
    <p class="hint" style="margin:11px 0 0">{hints}</p>
    <pre id="log">Nothing run yet. "Run checks" takes a couple of minutes; output appears as it goes.</pre>
  </div>

  <div class="card"><h2>Every macro, and the check behind it</h2>
    <div class="tools">
      <input type="search" id="q" placeholder="filter by name, value, check or description">
      <select id="pick"><option value="">every check</option>{options}</select>
      <label class="hint"><input type="checkbox" id="only"> only those the manuscript quotes</label>
      <span class="count" id="count"></span>
    </div>
    <table id="macros"><thead><tr>
      <th>macro</th><th>value</th><th>from</th><th></th><th>what it means</th>
    </tr></thead><tbody>{''.join(body)}</tbody></table>
  </div>
</div>
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
            self._send(json.dumps(provenance.compute(), default=str).encode(),
                       "application/json")
        else:
            self._send(render(provenance.compute()).encode(), "text/html; charset=utf-8")

    def do_POST(self) -> None:
        name = self.path.rsplit("/", 1)[-1]
        if name in JOBS and _job["done"]:
            threading.Thread(target=_run, args=(name,), daemon=True).start()
        self._send(b"{}", "application/json")

    def log_message(self, *_):                  # the page is the log
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
