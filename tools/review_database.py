"""Build a self-contained HTML review page for an extraction and the judge's verdicts on it.

The page is a two-pane reviewing tool, not a document: papers on the left, one paper's records on
the right. Records are one line each until opened, so a paper with seventy-five of them is still
a single screen. Opening a record shows its fields, the judge's verdict and reasoning, the
corrections it proposed, and the source text the record cites -- with the extracted values
highlighted inside that text, so a number can be checked against its sentence without opening
the paper.

A toggle switches every corrected field between the value the extractor wrote and the value the
judge proposed, so both versions of the database are reviewable from one file.

    review_database.py --extraction mass_luna --judge mass_oss/mass_oss
    review_database.py --extraction mass_oss/mass_oss_corrected --corpus corpus_markdown

Any extraction and judge run work, whatever models produced them, as long as the judge ran
against that extraction. Omit --judge to render an extraction on its own.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root importable
from core.paths import ARTIFACTS, RUNS_DIR, data_path
from core.utils import doi_to_filename

FIELDS = ["catalyst", "solvent", "temperature_c", "reaction_time_min", "catalyst_amount_g",
          "PET_amount_g", "solvent_amount_g", "yield_percent", "selectivity_percent",
          "conversion_percent", "pressure_atm"]

LABELS = {"catalyst": "catalyst", "solvent": "solvent", "temperature_c": "temp °C",
          "reaction_time_min": "time min", "catalyst_amount_g": "cat. g",
          "PET_amount_g": "PET g", "solvent_amount_g": "solv. g",
          "yield_percent": "yield %", "selectivity_percent": "select. %",
          "conversion_percent": "conv. %", "pressure_atm": "press. atm"}

SUMMARY_FIELDS = ["catalyst", "temperature_c", "reaction_time_min", "yield_percent"]

CHUNK_PATTERN = re.compile(r"^ID: ([0-9a-f-]{36})$", re.M)


def load_run(run_dir: Path, subdir: str) -> dict:
    """Every JSON file in a run subdirectory, keyed by the doi it records."""
    by_doi = {}
    for path in sorted((run_dir / subdir).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        by_doi[payload["doi"]] = payload
    return by_doi


def load_chunks(markdown_dir: Path, doi: str) -> dict:
    """Split a paper's markdown into {chunk id: text}, the form source_chunk_ids points at."""
    path = markdown_dir / doi_to_filename(doi.lower(), "md")
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    pieces = CHUNK_PATTERN.split(text)   # [preamble, id, body, id, body, ...]
    return {pieces[i]: pieces[i + 1].strip() for i in range(1, len(pieces) - 1, 2)}


def paper_title(chunks: dict) -> str:
    """The first substantial line of the paper, which the parser puts the title on."""
    for body in chunks.values():
        for line in body.splitlines():
            cleaned = line.strip().lstrip("#").strip()
            if len(cleaned) > 20:
                return cleaned[:180]
    return ""


def state_of(verdict: dict) -> str:
    """One word for what the judge decided, which drives colour and filtering."""
    if not verdict:
        return "unjudged"
    if verdict.get("verdict") == "correct":
        return "ok"
    if verdict.get("drop_record"):
        return "drop"
    return "fixed"


def build_payload(extraction: Path, judge: Path | None, markdown_dir: Path) -> tuple[list, dict]:
    """Everything the page needs, as plain data the browser renders."""
    extractions = load_run(extraction, "extractions")
    verdicts_by_doi = load_run(judge, "verdicts") if judge else {}

    papers = []
    counts = {"records": 0, "ok": 0, "fixed": 0, "drop": 0, "unjudged": 0, "unresolved": 0}

    for doi in sorted(extractions):
        records = extractions[doi]["records"]
        if not records:
            continue

        payload = verdicts_by_doi.get(doi, {})
        verdicts = {v["extracted_index"]: v for v in payload.get("verdicts", [])}
        chunks = load_chunks(markdown_dir, doi)

        cited_here = set()
        rows = []
        for index, record in enumerate(records):
            verdict = verdicts.get(index, {})
            state = state_of(verdict)
            counts["records"] += 1
            counts[state] += 1

            cited = record.get("source_chunk_ids") or []
            resolved = [c for c in cited if c in chunks]
            counts["unresolved"] += len(cited) - len(resolved)
            cited_here.update(resolved)

            rows.append({
                "i": index,
                "state": state,
                "values": {f: record.get(f) for f in FIELDS},
                "critique": verdict.get("critique") or "",
                "bad": verdict.get("bad_fields") or [],
                "fixes": [{"field": fix["field"], "to": fix["value"],
                           "evidence": fix.get("evidence") or ""}
                          for fix in (verdict.get("fixes") or [])],
                "cited": cited,
                "missing": [c for c in cited if c not in chunks],
            })

        papers.append({
            "doi": doi,
            "title": paper_title(chunks),
            "records": rows,
            # only the chunks this paper's records actually cite, so the page stays small
            "chunks": {c: chunks[c] for c in sorted(cited_here)},
        })

    return papers, counts


def build(extraction: Path, judge: Path | None, markdown_dir: Path, title: str) -> str:
    papers, counts = build_payload(extraction, judge, markdown_dir)

    judged = counts["records"] - counts["unjudged"]
    rate = f"{counts['ok'] / judged:.1%}" if judged else "n/a"
    tiles = [("papers", len(papers)), ("records", counts["records"]),
             ("accepted", counts["ok"]), ("corrected", counts["fixed"]),
             ("would drop", counts["drop"]), ("pass rate", rate)]

    data = {"papers": papers, "fields": FIELDS, "labels": LABELS, "summary": SUMMARY_FIELDS}

    # Plain substitution, not str.format: the template holds CSS braces and regex backslashes,
    # and doubling every one of them to survive .format() is how the highlighter broke once.
    page = TEMPLATE
    for token, value in [
        ("__TITLE__", html.escape(title)),
        ("__EXTRACTION__", html.escape(extraction.name)),
        ("__JUDGE__", html.escape(judge.name if judge else "not judged")),
        ("__TILES__", "".join(f'<div class="tile"><b>{value}</b><span>{name}</span></div>'
                              for name, value in tiles)),
        ("__PAYLOAD__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")),
    ]:
        page = page.replace(token, value)
    return page


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#eef2f1;--panel:#fff;--ink:#16211f;--dim:#61756f;--line:#d8e2df;--soft:#f5f8f7;
 --ok:#3f6e46;--ok-bg:#e3efe4;--fix:#8f5f10;--fix-bg:#f7ecd8;--drop:#a33a2e;--drop-bg:#f8e2dd;
 --accent:#0e7c6b;--mark:#ffe9a8;--markink:#4a3800}
@media(prefers-color-scheme:dark){:root{--bg:#0b1312;--panel:#131e1d;--ink:#dde7e4;--dim:#8ea29e;
 --line:#243432;--soft:#0f1918;--ok:#7fb187;--ok-bg:#16281a;--fix:#d6a054;--fix-bg:#2c2413;
 --drop:#d98374;--drop-bg:#2e1a16;--accent:#4fc4ae;--mark:#5d4c19;--markink:#ffeab5}}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);
 font:14.5px/1.5 ui-sans-serif,system-ui,-apple-system,sans-serif}
.app{display:grid;grid-template-columns:300px 1fr;height:100vh}
@media(max-width:820px){.app{grid-template-columns:1fr}#side{display:none}}

#side{border-right:1px solid var(--line);background:var(--panel);display:flex;
 flex-direction:column;min-height:0}
.brand{padding:16px 16px 12px;border-bottom:1px solid var(--line)}
.brand h1{font-size:1rem;margin:0 0 4px;line-height:1.3}
.brand p{margin:0;font-size:.74rem;color:var(--dim);font-family:ui-monospace,monospace}
#search{margin:12px 16px;padding:8px 10px;border:1px solid var(--line);border-radius:7px;
 background:var(--soft);color:var(--ink);font:inherit;font-size:.86rem}
#list{overflow-y:auto;flex:1;padding:0 8px 16px}
.item{padding:9px 10px;border-radius:7px;cursor:pointer;border:1px solid transparent}
.item:hover{background:var(--soft)}
.item.sel{background:var(--soft);border-color:var(--accent)}
.item .d{font-family:ui-monospace,monospace;font-size:.76rem;color:var(--accent);
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.item .t{font-size:.78rem;color:var(--dim);margin:2px 0 5px;
 display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.pips{display:flex;gap:3px;align-items:center}
.pip{height:4px;border-radius:2px;flex:0 0 auto}
.pip.ok{background:var(--ok)} .pip.fixed{background:var(--fix)} .pip.drop{background:var(--drop)}
.pip.unjudged{background:var(--line)}
.item .c{font-size:.7rem;color:var(--dim);margin-left:6px;font-variant-numeric:tabular-nums}

#main{overflow-y:auto;min-height:0;scroll-behavior:smooth}
.tiles{display:flex;gap:8px;flex-wrap:wrap;padding:16px 22px 0}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:9px 14px}
.tile b{display:block;font-size:1.15rem;font-variant-numeric:tabular-nums}
.tile span{font-size:.68rem;color:var(--dim);text-transform:uppercase;letter-spacing:.06em}

.head{position:sticky;top:0;z-index:4;background:var(--bg);padding:14px 22px 10px;
 border-bottom:1px solid var(--line)}
.head h2{margin:0 0 3px;font-size:.95rem;font-family:ui-monospace,monospace;color:var(--accent)}
.head p{margin:0 0 10px;font-size:.85rem;color:var(--dim)}
.tools{display:flex;gap:7px;flex-wrap:wrap;align-items:center}
.tools button{font:inherit;font-size:.78rem;padding:5px 11px;border:1px solid var(--line);
 border-radius:20px;background:var(--panel);color:var(--dim);cursor:pointer}
.tools button.on{background:var(--accent);border-color:var(--accent);color:#fff}

.recs{padding:6px 22px 60px}
.rec{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--line);
 border-radius:7px;margin-bottom:6px;overflow:hidden}
.rec.ok{border-left-color:var(--ok)} .rec.fixed{border-left-color:var(--fix)}
.rec.drop{border-left-color:var(--drop)}
.row{display:flex;gap:12px;align-items:center;padding:9px 13px;cursor:pointer}
.row:hover{background:var(--soft)}
.ix{font-family:ui-monospace,monospace;font-size:.74rem;color:var(--dim);width:34px;flex:0 0 auto}
.cat{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.88rem}
.mini{font-size:.78rem;color:var(--dim);font-variant-numeric:tabular-nums;white-space:nowrap}
.tag{font-size:.64rem;text-transform:uppercase;letter-spacing:.07em;padding:3px 8px;
 border-radius:4px;flex:0 0 auto}
.tag.ok{background:var(--ok-bg);color:var(--ok)}
.tag.fixed{background:var(--fix-bg);color:var(--fix)}
.tag.drop{background:var(--drop-bg);color:var(--drop)}
.tag.unjudged{background:var(--soft);color:var(--dim)}

.body{display:none;padding:2px 13px 14px;border-top:1px solid var(--line)}
.rec.open .body{display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(132px,1fr));gap:6px;margin:11px 0}
.cell{background:var(--soft);border:1px solid var(--line);border-radius:5px;padding:5px 8px}
.cell k{display:block;font-size:.63rem;color:var(--dim);text-transform:uppercase;letter-spacing:.05em}
.cell v{font-size:.85rem;font-variant-numeric:tabular-nums}
.cell.bad{border-color:var(--fix);background:var(--fix-bg)}
.cell .was{text-decoration:line-through;color:var(--dim);margin-right:5px}
.null{color:var(--dim);font-style:italic;font-size:.9em}
.crit{font-size:.86rem;color:var(--dim);border-left:2px solid var(--line);padding-left:11px;margin:0 0 11px}
.fx{margin:0 0 11px;padding-left:17px;font-size:.84rem}
.fx li{margin-bottom:5px}
.ev{color:var(--dim);font-size:.93em}
.srcs summary{cursor:pointer;font-size:.78rem;color:var(--dim)}
.src{margin-top:8px;border-left:2px solid var(--line);padding-left:11px}
.src .cid{font-family:ui-monospace,monospace;font-size:.68rem;color:var(--dim)}
.src .txt{white-space:pre-wrap;font-size:.82rem;color:var(--dim);max-height:220px;
 overflow:auto;margin-top:3px}
.gone{color:var(--drop);font-size:.8rem;margin-top:7px}
mark{background:var(--mark);color:var(--markink);border-radius:2px;padding:0 2px}
.empty{padding:40px 22px;color:var(--dim)}
</style></head><body>
<div class="app">
  <aside id="side">
    <div class="brand"><h1>__TITLE__</h1><p>__EXTRACTION__ · __JUDGE__</p></div>
    <input id="search" placeholder="filter papers…" autocomplete="off">
    <div id="list"></div>
  </aside>
  <main id="main">
    <div class="tiles">__TILES__</div>
    <div id="pane"></div>
  </main>
</div>
<script id="data" type="application/json">__PAYLOAD__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const {papers, fields, labels, summary} = DATA;
const list = document.getElementById('list'), pane = document.getElementById('pane');
const search = document.getElementById('search');
let selected = 0, filter = '', corrected = false;

const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]);
const fmt = v => v === null || v === undefined
  ? '<span class="null">not reported</span>'
  : esc(typeof v === 'number' && Number.isInteger(v) ? v : v);

function forms(v) {
  if (v === null || v === undefined) return [];
  if (typeof v === 'string') return v.length > 2 ? [v] : [];
  const out = new Set([String(v)]);
  if (Number.isInteger(v)) out.add(String(v)); else out.add(v.toFixed(1).replace(/\\.0$/, ''));
  return [...out].filter(s => s.length > 1);
}

// The needle is escaped for HTML first, because the text being searched is already escaped,
// then escaped again for use inside a regex. No lookbehind: unsupported on older Safari, so the
// leading boundary is captured and put back.
const RX_SPECIAL = /[.*+?^${}()|[\]\\]/g;

function mark(text, values) {
  const wanted = [];
  for (const f of fields) for (const s of forms(values[f])) wanted.push(s);
  wanted.sort((a, b) => b.length - a.length);

  let out = esc(text);
  for (const s of wanted) {
    const needle = esc(s).replace(RX_SPECIAL, '\\$&');
    const re = new RegExp('(^|[^\\w.])(' + needle + ')(?![\\w.])', 'g');
    let hits = 0;
    out = out.replace(re, (whole, before, hit) =>
      hits++ < 3 ? before + '<mark>' + hit + '</mark>' : whole);
  }
  return out;
}

function paperCounts(p) {
  const c = {ok: 0, fixed: 0, drop: 0, unjudged: 0};
  for (const r of p.records) c[r.state]++;
  return c;
}

function drawList() {
  const needle = filter.toLowerCase();
  list.innerHTML = '';
  papers.forEach((p, i) => {
    if (needle && !(p.doi + ' ' + p.title).toLowerCase().includes(needle)) return;
    const c = paperCounts(p), n = p.records.length;
    const pips = ['ok', 'fixed', 'drop', 'unjudged']
      .filter(k => c[k]).map(k => `<i class="pip ${k}" style="width:${c[k] / n * 100}%"></i>`).join('');
    const el = document.createElement('div');
    el.className = 'item' + (i === selected ? ' sel' : '');
    el.innerHTML = `<div class="d">${esc(p.doi)}</div><div class="t">${esc(p.title)}</div>
      <div class="pips">${pips}<span class="c">${n}</span></div>`;
    el.onclick = () => { selected = i; drawList(); drawPaper(); document.getElementById('main').scrollTop = 0; };
    list.appendChild(el);
  });
  if (!list.children.length) list.innerHTML = '<p class="empty">no papers match</p>';
}

function drawPaper() {
  const p = papers[selected];
  if (!p) { pane.innerHTML = '<p class="empty">nothing to show</p>'; return; }

  const rows = p.records.map(r => {
    const v = r.values;
    const fixMap = Object.fromEntries(r.fixes.map(f => [f.field, f]));
    const cells = fields.map(f => {
      const has = f in fixMap;
      const shown = corrected && has
        ? `<span class="was">${fmt(v[f])}</span>${fmt(fixMap[f].to)}`
        : fmt(v[f]);
      return `<div class="cell${r.bad.includes(f) ? ' bad' : ''}">
        <k>${labels[f]}</k><v>${shown}</v></div>`;
    }).join('');

    const fixes = r.fixes.length ? `<ul class="fx">${r.fixes.map(f =>
      `<li><b>${labels[f.field] || f.field}</b>: ${fmt(v[f.field])} &rarr; ${fmt(f.to)}
       <br><span class="ev">${esc(f.evidence)}</span></li>`).join('')}</ul>` : '';

    const srcs = r.cited.filter(c => p.chunks[c]).map(c =>
      `<div class="src"><div class="cid">${c.slice(0, 8)}</div>
       <div class="txt">${mark(p.chunks[c], v)}</div></div>`).join('');
    const gone = r.missing.length
      ? `<div class="gone">${r.missing.length} cited chunk${r.missing.length > 1 ? 's' : ''} not found in this paper</div>`
      : '';

    const mini = summary.slice(1).map(f => v[f] === null ? '—' : v[f]).join(' · ');
    return `<div class="rec ${r.state}" data-state="${r.state}">
      <div class="row"><span class="ix">#${r.i}</span>
        <span class="cat">${fmt(v.catalyst)}</span>
        <span class="mini">${esc(mini)}</span>
        <span class="tag ${r.state}">${r.state === 'ok' ? 'accepted' : r.state === 'fixed' ? 'corrected' : r.state === 'drop' ? 'would drop' : 'unjudged'}</span></div>
      <div class="body">
        <div class="grid">${cells}</div>
        ${r.critique ? `<p class="crit">${esc(r.critique)}</p>` : ''}
        ${fixes}
        ${srcs ? `<details class="srcs"><summary>${r.cited.length} source chunk${r.cited.length > 1 ? 's' : ''}</summary>${srcs}</details>` : ''}
        ${gone}
      </div></div>`;
  }).join('');

  pane.innerHTML = `<div class="head">
      <h2>${esc(p.doi)}</h2><p>${esc(p.title)}</p>
      <div class="tools">
        <button data-f="" class="on">all ${p.records.length}</button>
        <button data-f="ok">accepted</button>
        <button data-f="fixed">corrected</button>
        <button data-f="drop">would drop</button>
        <button id="corr" class="${corrected ? 'on' : ''}">${corrected ? 'showing corrected' : 'show corrected'}</button>
        <button id="all">expand all</button>
      </div></div>
    <div class="recs">${rows}</div>`;

  pane.querySelectorAll('.row').forEach(row =>
    row.onclick = () => row.parentElement.classList.toggle('open'));

  pane.querySelectorAll('.tools button[data-f]').forEach(btn => btn.onclick = () => {
    pane.querySelectorAll('.tools button[data-f]').forEach(b => b.classList.remove('on'));
    btn.classList.add('on');
    const want = btn.dataset.f;
    pane.querySelectorAll('.rec').forEach(rec =>
      rec.style.display = (!want || rec.dataset.state === want) ? '' : 'none');
  });

  document.getElementById('corr').onclick = () => { corrected = !corrected; drawPaper(); };
  document.getElementById('all').onclick = e => {
    const on = !e.target.classList.contains('on');
    e.target.classList.toggle('on', on);
    e.target.textContent = on ? 'collapse all' : 'expand all';
    pane.querySelectorAll('.rec').forEach(r => r.classList.toggle('open', on));
  };
}

search.addEventListener('input', e => { filter = e.target.value; drawList(); });
drawList(); drawPaper();
</script>
</body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(prog="review_database")
    parser.add_argument("--extraction", required=True,
                        help="extraction run under artifacts/runs, e.g. mass_luna")
    parser.add_argument("--judge", default=None,
                        help="judge run under artifacts/runs, e.g. mass_oss/mass_oss")
    parser.add_argument("--corpus", default="corpus_markdown",
                        help="chunked markdown directory under artifacts/data")
    parser.add_argument("--out", default=None, help="output HTML path")
    parser.add_argument("--title", default="PET depolymerisation database")
    args = parser.parse_args()

    extraction = RUNS_DIR / args.extraction
    judge = RUNS_DIR / args.judge if args.judge else None
    if not (extraction / "extractions").is_dir():
        parser.error(f"no extractions/ in {extraction}")
    if judge and not (judge / "verdicts").is_dir():
        parser.error(f"no verdicts/ in {judge}")

    page = build(extraction, judge, data_path(args.corpus), args.title)
    default = ARTIFACTS / f"review_{args.extraction.replace('/', '_')}.html"
    out = Path(args.out) if args.out else default
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
