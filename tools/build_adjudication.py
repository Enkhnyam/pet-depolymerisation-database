"""Collect the records the two graders disagree about, for a human to adjudicate.

Only records where exactly one grader matched the human carry information about which grader is
better. A record the graders already disagree on is guaranteed to become one of those once it is
labelled, because one of them must be the one that matched -- so this is the cheapest possible
labelling set. Adjudicating a random sample is what made the existing 48-record set yield only
four informative pairs.

This needs a curated answer key, because the metric grader has no verdict without one. It
therefore runs on a benchmark extraction over the curated papers, not on the mass corpus.

    build_adjudication.py --extraction extract_luna/extract_luna_n4_r1 \\
                          --judge judge_oss_on_luna/judge_oss_on_luna

Writes an HTML page where a chemist marks each record correct or incorrect without being shown
either grader's verdict, and exports the decisions as JSON. Feed that JSON back as a golden set
and checks/judge/significance.py will test it.
"""
import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))       # repo root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "checks"))
from _setup import RUNS_DIR, judged, scored
from core.paths import ARTIFACTS, data_path
from review_database import FIELDS, LABELS, load_chunks, load_run, paper_title


def collect(extraction: Path, judge: Path, markdown_dir: Path, evaluable_only: bool) -> list:
    """Every record whose two graders disagree, with the text needed to judge it."""
    metric = scored(run=extraction)
    verdicts = judged(run=judge)
    both = metric.merge(verdicts, on=["doi", "index"])
    if evaluable_only:
        both = both[both.situation != "no curated counterpart"]

    disputed = both[both.metric != both.judge]
    extractions = load_run(extraction, "extractions")

    items = []
    for row in disputed.itertuples():
        records = extractions[row.doi]["records"]
        if row.index >= len(records):
            continue
        chunks = load_chunks(markdown_dir, row.doi)
        record = records[row.index]
        cited = [c for c in (record.get("source_chunk_ids") or []) if c in chunks]

        items.append({
            "doi": row.doi,
            "index": int(row.index),
            "title": paper_title(chunks),
            "situation": row.situation,
            "values": {f: record.get(f) for f in FIELDS},
            "chunks": [{"id": c, "text": chunks[c]} for c in cited],
            # deliberately not exported: what either grader said, so the labeller is not anchored
        })
    return items


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#eef2f1;--panel:#fff;--ink:#16211f;--dim:#61756f;--line:#d8e2df;--soft:#f5f8f7;
 --ok:#3f6e46;--no:#a33a2e;--accent:#0e7c6b;--mark:#ffe9a8;--markink:#4a3800}
@media(prefers-color-scheme:dark){:root{--bg:#0b1312;--panel:#131e1d;--ink:#dde7e4;--dim:#8ea29e;
 --line:#243432;--soft:#0f1918;--ok:#7fb187;--no:#d98374;--accent:#4fc4ae;--mark:#5d4c19;--markink:#ffeab5}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 ui-sans-serif,system-ui,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:26px 20px 90px}
h1{font-size:1.3rem;margin:0 0 5px}
.sub{color:var(--dim);font-size:.9rem;margin:0 0 20px}
.bar{position:sticky;top:0;background:var(--bg);padding:12px 0;border-bottom:1px solid var(--line);
 z-index:5;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.prog{font-variant-numeric:tabular-nums;font-size:.9rem}
button{font:inherit;font-size:.85rem;padding:6px 13px;border:1px solid var(--line);
 border-radius:7px;background:var(--panel);color:var(--ink);cursor:pointer}
button.export{background:var(--accent);border-color:var(--accent);color:#fff}
.card{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:16px;margin:14px 0}
.doi{font-family:ui-monospace,monospace;font-size:.78rem;color:var(--accent)}
.ttl{color:var(--dim);font-size:.85rem;margin:3px 0 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(136px,1fr));gap:6px;margin-bottom:13px}
.cell{background:var(--soft);border:1px solid var(--line);border-radius:5px;padding:5px 8px}
.cell k{display:block;font-size:.63rem;color:var(--dim);text-transform:uppercase;letter-spacing:.05em}
.cell v{font-size:.86rem;font-variant-numeric:tabular-nums}
.null{color:var(--dim);font-style:italic;font-size:.9em}
.src{border-left:2px solid var(--line);padding-left:11px;margin-top:9px}
.src .cid{font-family:ui-monospace,monospace;font-size:.67rem;color:var(--dim)}
.src .txt{white-space:pre-wrap;font-size:.83rem;color:var(--dim);max-height:240px;overflow:auto;margin-top:3px}
mark{background:var(--mark);color:var(--markink);border-radius:2px;padding:0 2px}
.ask{margin-top:14px;padding-top:13px;border-top:1px solid var(--line);display:flex;gap:9px;align-items:center;flex-wrap:wrap}
.ask span{font-size:.87rem;color:var(--dim);margin-right:4px}
.vote.yes.on{background:var(--ok);border-color:var(--ok);color:#fff}
.vote.no.on{background:var(--no);border-color:var(--no);color:#fff}
.note{flex:1;min-width:160px;padding:6px 9px;border:1px solid var(--line);border-radius:6px;
 background:var(--soft);color:var(--ink);font:inherit;font-size:.83rem}
.done{opacity:.55}
</style></head><body><div class="wrap">
<h1>__TITLE__</h1>
<p class="sub">Each record below is one the two graders disagreed about. Decide only this: is the
record a faithful description of an experiment the paper reports? Neither grader's verdict is
shown, so your answer is not anchored to either.</p>
<div class="bar">
  <span class="prog" id="prog"></span>
  <button id="next">jump to next undecided</button>
  <button class="export" id="export">export decisions</button>
</div>
<div id="cards"></div>
</div>
<script id="data" type="application/json">__PAYLOAD__</script>
<script>
const ITEMS = JSON.parse(document.getElementById('data').textContent);
const KEY = 'adjudication-__SLUG__';
const saved = JSON.parse(localStorage.getItem(KEY) || '{}');
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]);
const fmt = v => v === null || v === undefined ? '<span class="null">not reported</span>' : esc(v);
const RX = /[.*+?^${}()|[\]\\]/g;

function forms(v){
  if (v === null || v === undefined) return [];
  if (typeof v === 'string') return v.length > 2 ? [v] : [];
  const out = new Set([String(v)]);
  if (Number.isInteger(v)) out.add(String(v)); else out.add(v.toFixed(1).replace(/\.0$/, ''));
  return [...out].filter(s => s.length > 1);
}
function mark(text, values){
  const wanted = [];
  for (const k in values) for (const s of forms(values[k])) wanted.push(s);
  wanted.sort((a,b) => b.length - a.length);
  let out = esc(text);
  for (const s of wanted){
    const re = new RegExp('(^|[^\\w.])(' + esc(s).replace(RX,'\\$&') + ')(?![\\w.])','g');
    let n = 0;
    out = out.replace(re, (w,b,h) => n++ < 3 ? b + '<mark>' + h + '</mark>' : w);
  }
  return out;
}
function key(it){ return it.doi + '#' + it.index; }

function progress(){
  const done = ITEMS.filter(it => saved[key(it)]?.human).length;
  document.getElementById('prog').textContent = done + ' of ' + ITEMS.length + ' decided';
}

const cards = document.getElementById('cards');
ITEMS.forEach((it, n) => {
  const k = key(it);
  const cells = Object.keys(it.values).map(f =>
    `<div class="cell"><k>${esc(LABELS[f] || f)}</k><v>${fmt(it.values[f])}</v></div>`).join('');
  const srcs = it.chunks.map(c =>
    `<div class="src"><div class="cid">${esc(c.id.slice(0,8))}</div>
     <div class="txt">${mark(c.text, it.values)}</div></div>`).join('')
    || '<p class="null">this record cites no source chunk</p>';

  const el = document.createElement('div');
  el.className = 'card'; el.id = 'c' + n;
  el.innerHTML = `<div class="doi">${esc(it.doi)} &middot; record #${it.index}</div>
    <div class="ttl">${esc(it.title)}</div>
    <div class="grid">${cells}</div>${srcs}
    <div class="ask"><span>Faithful to the paper?</span>
      <button class="vote yes">yes</button><button class="vote no">no</button>
      <input class="note" placeholder="note (optional)"></div>`;

  const yes = el.querySelector('.yes'), no = el.querySelector('.no'), note = el.querySelector('.note');
  const paint = () => {
    const rec = saved[k] || {};
    yes.classList.toggle('on', rec.human === 'correct');
    no.classList.toggle('on', rec.human === 'incorrect');
    el.classList.toggle('done', !!rec.human);
    if (rec.note) note.value = rec.note;
  };
  const set = v => {
    saved[k] = {doi: it.doi, extracted_index: it.index, human: v, note: note.value || null};
    localStorage.setItem(KEY, JSON.stringify(saved));
    paint(); progress();
  };
  yes.onclick = () => set('correct');
  no.onclick = () => set('incorrect');
  note.onchange = () => { if (saved[k]) set(saved[k].human); };
  paint();
  cards.appendChild(el);
});
progress();

document.getElementById('next').onclick = () => {
  const i = ITEMS.findIndex(it => !saved[key(it)]?.human);
  if (i >= 0) document.getElementById('c' + i).scrollIntoView({behavior:'smooth', block:'center'});
};
document.getElementById('export').onclick = () => {
  const out = ITEMS.filter(it => saved[key(it)]?.human).map(it => saved[key(it)]);
  const text = JSON.stringify(out, null, 2);
  navigator.clipboard?.writeText(text);
  const w = window.open('', '_blank');
  if (w) { w.document.title = 'decisions.json'; w.document.body.innerText = text; }
  else alert(text);
};
const LABELS = __LABELS__;
</script></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(prog="build_adjudication")
    parser.add_argument("--extraction", required=True, help="benchmark extraction run")
    parser.add_argument("--judge", required=True, help="judge run against that extraction")
    parser.add_argument("--corpus", default="curated_data_markdown_by_doi")
    parser.add_argument("--all", action="store_true",
                        help="include records the metric had no counterpart for")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    extraction = RUNS_DIR / args.extraction
    judge = RUNS_DIR / args.judge
    items = collect(extraction, judge, data_path(args.corpus), evaluable_only=not args.all)

    slug = f"{Path(args.judge).name}-on-{Path(args.extraction).name}"
    title = f"Adjudication — {slug}"
    page = TEMPLATE
    for token, value in [("__TITLE__", html.escape(title)),
                         ("__SLUG__", slug),
                         ("__LABELS__", json.dumps(LABELS)),
                         ("__PAYLOAD__", json.dumps(items, ensure_ascii=False).replace("</", "<\\/"))]:
        page = page.replace(token, value)

    out = Path(args.out) if args.out else ARTIFACTS / f"adjudicate_{slug}.html"
    out.write_text(page, encoding="utf-8")
    print(f"{len(items)} disagreements to adjudicate")
    print(f"wrote {out}  ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
