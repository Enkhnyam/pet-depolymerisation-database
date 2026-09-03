"""Build the adjudication worklist as a two-pane reading tool.

The paper on the left, rendered as markdown so its tables survive -- reaction conditions live in
tables, and a pane that flattened them would be useless for exactly the records that are hardest
to judge. The records on the right.

Selecting a record marks the chunks it was read from and highlights, inside those chunks, the
values it claims. So "did the model read this correctly" is answered by looking at one screen
rather than by hunting through a PDF.

What either grader said is shown nowhere: a labeller who can see a verdict is checking it rather
than forming a view. Records already ruled on in the rescue review arrive with that answer filled
in, marked as carried over and changeable.

Three strata: every disagreement, every record both graders flagged, and a sample of the records
both accepted. The first two are censuses because precision is measured on flagged records and
there are few of them; the sample is what recall needs. See checks/human/worklist.py.

    build_adjudication.py                     every flagged record plus 50 accepted ones
    build_adjudication.py --agreements 20     a smaller sample of the accepted records
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "checks"))
from _markdown import render
from _page import validate
from core.paths import ARTIFACTS, data_path
from core.utils import doi_to_filename
from human import worklist as worklist_check
from review_database import FIELDS, LABELS, load_run, paper_title

CHUNK_PATTERN = re.compile(r"^ID: ([0-9a-f-]{36})$", re.M)


def chunks_of(markdown_dir: Path, doi: str) -> list:
    """The paper's chunks in order, each rendered to html."""
    path = markdown_dir / doi_to_filename(doi.lower(), "md")
    if not path.exists():
        return []
    pieces = CHUNK_PATTERN.split(path.read_text(encoding="utf-8"))
    return [{"id": pieces[i], "html": render(pieces[i + 1])}
            for i in range(1, len(pieces) - 1, 2)]


def build(markdown_dir: Path, agreements: int) -> tuple[str, dict]:
    worklist_check.AGREEMENTS = agreements
    sample = worklist_check.compute()
    extractions = load_run(worklist_check.EXTRACTION, "extractions")

    papers = {}
    for row in sample.itertuples():
        paper = extractions.get(row.doi)
        if paper is None or row.index >= len(paper["records"]):
            continue
        entry = papers.setdefault(row.doi, {"doi": row.doi, "chunks": [], "records": []})
        record = paper["records"][row.index]
        entry["records"].append({
            "index": int(row.index),
            "stratum": row.stratum,
            "dispute": row.dispute,
            "weight": float(row.weight),
            "prefilled": row.prefilled,
            "values": {field: record.get(field) for field in FIELDS},
            "cites": record.get("source_chunk_ids") or [],
        })

    for doi, entry in papers.items():
        entry["chunks"] = chunks_of(markdown_dir, doi)
        entry["title"] = paper_title(
            {c["id"]: re.sub(r"<[^>]+>", " ", c["html"]) for c in entry["chunks"]})
        entry["records"].sort(key=lambda r: r["index"])

    ordered = sorted(papers.values(), key=lambda p: -len(p["records"]))
    counts = {
        "papers": len(ordered),
        "records": sum(len(p["records"]) for p in ordered),
        "prefilled": sum(1 for p in ordered for r in p["records"] if r["prefilled"]),
    }
    counts["to decide"] = counts["records"] - counts["prefilled"]

    page = TEMPLATE
    for token, value in [
        ("__AGREEMENTS__", str(agreements)),
        ("__COUNTS__", json.dumps(counts)),
        ("__LABELS__", json.dumps(LABELS)),
        ("__DATA__", json.dumps(ordered, ensure_ascii=False).replace("</", "<\\/")),
    ]:
        page = page.replace(token, value)
    return page, counts


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Adjudication worklist</title>
<style>
:root{--bg:#eef2f1;--panel:#fff;--ink:#16211f;--dim:#61756f;--line:#d8e2df;--soft:#f5f8f7;
 --ok:#3f6e46;--no:#a33a2e;--accent:#0e7c6b;--mark:#ffe08a;--markink:#4a3400;
 --cite:#fff8e6;--citeline:#e0b93c}
@media(prefers-color-scheme:dark){:root{--bg:#0b1312;--panel:#131e1d;--ink:#dde7e4;--dim:#8ea29e;
 --line:#243432;--soft:#0f1918;--ok:#7fb187;--no:#d98374;--accent:#4fc4ae;--mark:#6b5410;
 --markink:#ffeab5;--cite:#1d2417;--citeline:#7a6420}}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);
 font:14.5px/1.6 ui-sans-serif,system-ui,-apple-system,sans-serif}
.app{display:grid;grid-template-rows:auto 1fr;height:100vh}
header{display:flex;gap:14px;align-items:center;flex-wrap:wrap;padding:10px 16px;
 background:var(--panel);border-bottom:1px solid var(--line)}
header h1{font-size:.95rem;margin:0;font-weight:600}
select,button,input{font:inherit;font-size:.85rem;padding:6px 10px;border:1px solid var(--line);
 border-radius:7px;background:var(--panel);color:var(--ink)}
select{max-width:44ch}
button{cursor:pointer}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.grow{flex:1}
.muted{color:var(--dim);font-size:.82rem}
main{display:grid;grid-template-columns:1fr 1fr;min-height:0}
@media(max-width:1000px){main{grid-template-columns:1fr}}
#text,#recs{overflow-y:auto;padding:16px 20px;min-height:0}
#text{border-right:1px solid var(--line);background:var(--panel)}
.chunk{padding:2px 10px;border-left:3px solid transparent;border-radius:4px;margin-bottom:2px}
.chunk.cited{background:var(--cite);border-left-color:var(--citeline)}
.chunk h3,.chunk h4,.chunk h5,.chunk h6{font-size:.92rem;margin:14px 0 6px}
.chunk p{margin:0 0 8px}
.chunk ul{margin:0 0 8px;padding-left:20px}
.chunk table{border-collapse:collapse;width:100%;margin:8px 0;font-size:.82rem;display:block;
 overflow-x:auto}
.chunk th,.chunk td{border:1px solid var(--line);padding:4px 7px;text-align:left;
 white-space:nowrap}
.chunk th{background:var(--soft);font-weight:600}
mark{background:var(--mark);color:var(--markink);border-radius:2px;padding:0 2px;font-weight:600}
.rec{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--line);
 border-radius:8px;padding:12px 14px;margin-bottom:10px;cursor:pointer}
.rec.on{border-left-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.rec.done{opacity:.62}
.rechead{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.ix{font-family:ui-monospace,monospace;font-size:.76rem;color:var(--dim)}
.tag{font-size:.64rem;text-transform:uppercase;letter-spacing:.06em;padding:2px 7px;
 border-radius:4px;background:var(--soft);color:var(--dim)}
.tag.disagree{background:#f7ecd8;color:#8a6318}
.tag.carried{background:#e3efe4;color:#2f6b41}
@media(prefers-color-scheme:dark){.tag.disagree{background:#2c2413;color:#d6a054}
 .tag.carried{background:#16281a;color:#7fb187}}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(124px,1fr));gap:5px;
 margin-bottom:10px}
.cell{background:var(--soft);border:1px solid var(--line);border-radius:5px;padding:4px 7px}
.cell k{display:block;font-size:.61rem;color:var(--dim);text-transform:uppercase;
 letter-spacing:.05em}
.cell v{font-size:.83rem;font-variant-numeric:tabular-nums}
.null{color:var(--dim);font-style:italic;font-size:.9em}
.ask{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding-top:9px;
 border-top:1px solid var(--line)}
.ask span{font-size:.83rem;color:var(--dim)}
.vote.yes.on{background:var(--ok);border-color:var(--ok);color:#fff}
.vote.no.on{background:var(--no);border-color:var(--no);color:#fff}
.note{flex:1;min-width:130px;font-size:.8rem}
</style></head><body>
<div class="app">
<header>
  <h1>Adjudication</h1>
  <select id="pick"></select>
  <span class="muted" id="stat"></span>
  <span class="grow"></span>
  <span class="muted" id="progress"></span>
  <button class="primary" id="export">Download decisions</button>
</header>
<main><div id="text"></div><div id="recs"></div></main>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const PAPERS = JSON.parse(document.getElementById('data').textContent);
const LABELS = __LABELS__;
const COUNTS = __COUNTS__;
const KEY = 'adjudication-benchmark-__AGREEMENTS__';
const saved = JSON.parse(localStorage.getItem(KEY) || '{}');
const CARRY = {real: 'correct', notreal: 'incorrect'};
const RX_SPECIAL = /[.*+?^${}()|[\]\\]/g;

for (const p of PAPERS) for (const r of p.records) {
  const k = p.doi + '#' + r.index;
  if (!saved[k] && CARRY[r.prefilled]) {
    saved[k] = {doi: p.doi, extracted_index: r.index, human: CARRY[r.prefilled],
                stratum: r.stratum, weight: r.weight, note: null, carried_over: true};
  }
}

let current = 0;
const esc = s => String(s).replace(/[&<>"]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]);
const fmt = v => v === null || v === undefined
  ? '<span class="null">not reported</span>' : esc(v);

function forms(v) {
  if (v === null || v === undefined) return [];
  if (typeof v === 'string') return v.length > 2 ? [v] : [];
  const out = new Set([String(v)]);
  if (Number.isInteger(v)) out.add(String(v));
  else out.add(v.toFixed(1).replace(/\.0$/, ''));
  return [...out].filter(s => s.length > 1);
}

// highlight inside text nodes only, so a value never lands inside a tag or a table border
function highlight(root, values) {
  const wanted = [];
  for (const f in values) for (const s of forms(values[f])) wanted.push(s);
  wanted.sort((a, b) => b.length - a.length);
  if (!wanted.length) return;
  const source = '(^|[^\\w.])(' +
    wanted.map(s => s.replace(RX_SPECIAL, '\\$&')).join('|') + ')(?![\\w.])';

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const pattern = new RegExp(source, 'g');
    if (!pattern.test(node.nodeValue)) continue;
    const span = document.createElement('span');
    span.innerHTML = esc(node.nodeValue).replace(new RegExp(source, 'g'), '$1<mark>$2</mark>');
    node.parentNode.replaceChild(span, node);
  }
}

function paperText(p) {
  return p.chunks.map(c => `<div class="chunk" data-id="${c.id}">${c.html}</div>`).join('')
    || '<p class="null">no text for this paper</p>';
}

function drawPaper() {
  const p = PAPERS[current];
  document.getElementById('stat').textContent =
    p.records.length + ' record' + (p.records.length === 1 ? '' : 's');
  document.getElementById('text').innerHTML = paperText(p);

  document.getElementById('recs').innerHTML = p.records.map(r => {
    const rec = saved[p.doi + '#' + r.index] || {};
    const cells = Object.keys(r.values).map(f =>
      `<div class="cell"><k>${esc(LABELS[f] || f)}</k><v>${fmt(r.values[f])}</v></div>`).join('');
    const tags = `<span class="tag ${r.stratum === 'graders disagree' ? 'disagree' : ''}">`
      + esc(r.dispute) + '</span>'
      + (rec.carried_over ? '<span class="tag carried">carried over</span>' : '');
    return `<div class="rec${rec.human ? ' done' : ''}" data-i="${r.index}">
      <div class="rechead"><span class="ix">#${r.index}</span>${tags}</div>
      <div class="grid">${cells}</div>
      <div class="ask"><span>Faithful to the paper?</span>
        <button class="vote yes${rec.human === 'correct' ? ' on' : ''}">yes</button>
        <button class="vote no${rec.human === 'incorrect' ? ' on' : ''}">no</button>
        <input class="note" placeholder="note (optional)" value="${esc(rec.note || '')}">
      </div></div>`;
  }).join('');

  document.querySelectorAll('#recs .rec').forEach(el => {
    const index = Number(el.dataset.i);
    const record = p.records.find(r => r.index === index);
    const k = p.doi + '#' + index;
    el.addEventListener('click', event => {
      if (event.target.tagName === 'BUTTON' || event.target.tagName === 'INPUT') return;
      select(record, el);
    });
    el.querySelector('.yes').onclick = () => decide(k, record, 'correct', el);
    el.querySelector('.no').onclick = () => decide(k, record, 'incorrect', el);
    el.querySelector('.note').onchange = e => {
      if (saved[k]) { saved[k].note = e.target.value || null; store(); }
    };
  });

  if (p.records.length) select(p.records[0], document.querySelector('#recs .rec'));
  progress();
}

function select(record, element) {
  document.querySelectorAll('#recs .rec').forEach(el => el.classList.remove('on'));
  if (element) element.classList.add('on');

  const p = PAPERS[current];
  document.getElementById('text').innerHTML = paperText(p);
  const cited = new Set(record.cites);
  let first = null;
  document.querySelectorAll('#text .chunk').forEach(el => {
    if (!cited.has(el.dataset.id)) return;
    el.classList.add('cited');
    highlight(el, record.values);
    if (!first) first = el;
  });
  if (first) first.scrollIntoView({behavior: 'smooth', block: 'center'});
}

function decide(key, record, answer, element) {
  const p = PAPERS[current];
  saved[key] = {doi: p.doi, extracted_index: record.index, human: answer,
                stratum: record.stratum, weight: record.weight,
                note: element.querySelector('.note').value || null, carried_over: false};
  store();
  element.querySelector('.yes').classList.toggle('on', answer === 'correct');
  element.querySelector('.no').classList.toggle('on', answer === 'incorrect');
  element.classList.add('done');
  progress();
}

function store() { localStorage.setItem(KEY, JSON.stringify(saved)); }

function progress() {
  document.getElementById('progress').textContent =
    `${Object.keys(saved).length} of ${COUNTS.records} decided `
    + `(${COUNTS.prefilled} carried over)`;
}

const pick = document.getElementById('pick');
PAPERS.forEach((p, i) => {
  const option = document.createElement('option');
  option.value = i;
  option.textContent = `${p.doi} — ${(p.title || '').slice(0, 60)}`;
  pick.appendChild(option);
});
pick.onchange = e => { current = Number(e.target.value); drawPaper(); };

document.getElementById('export').onclick = () => {
  const text = JSON.stringify({generated: new Date().toISOString(),
                               sample: COUNTS, decisions: Object.values(saved)}, null, 2);
  navigator.clipboard?.writeText(text);
  const w = window.open('', '_blank');
  if (w) { w.document.title = 'decisions.json'; w.document.body.innerText = text; }
  else alert(text);
};

drawPaper();
</script>
</body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(prog="build_adjudication")
    parser.add_argument("--corpus", default="curated_data_markdown_by_doi")
    parser.add_argument("--agreements", type=int, default=50,
                        help="how many accepted records to sample alongside every flagged one")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    page, counts = build(data_path(args.corpus), args.agreements)
    validate(page)
    out = Path(args.out) if args.out else ARTIFACTS / f"adjudicate_{args.agreements}agree.html"
    out.write_text(page, encoding="utf-8")

    print(f"{counts['records']} records across {counts['papers']} papers")
    print(f"  carried over from the rescue review  {counts['prefilled']}")
    print(f"  needing a decision                   {counts['to decide']}")
    print(f"wrote {out}  ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
