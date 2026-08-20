"""Review page for the records the metric marked wrong only because the table had no counterpart.

If one of these is a genuine experiment the curated table missed, the metric could not have been
right about it and the disagreement says nothing about the graders. If it is not, the metric was
right and the disagreement is real. Only a chemist reading the paper can tell the two apart, and
the headline agreement rate depends on which it is.
"""
import glob
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _setup import (ARTIFACTS, RUNS_DIR, data_path, as_experiments,
                    accept_threshold, catalyst_threshold, numeric_tolerance)
from core.evaluation import evaluate
from core.schema import load_curated

EXTRACTION = "luna"         # the model the mass run will use
JUDGE = "oss"
ALL_JUDGES = ["oss", "luna", "terra"]
FIELDS = ["catalyst", "solvent", "product", "temperature_c", "reaction_time_min",
          "catalyst_amount_g", "PET_amount_g", "solvent_amount_g",
          "yield_percent", "selectivity_percent", "conversion_percent", "pressure_atm"]

reference = load_curated(data_path("curated_table_final.json"))
_, labels = evaluate(reference, as_experiments(f"extract_{EXTRACTION}/extract_{EXTRACTION}_n4_r1"),
                     accept_threshold, catalyst_threshold, numeric_tolerance)
frame = pd.DataFrame(labels)
frame = frame[frame.extracted_index.notna()].copy()
frame["index"] = frame.extracted_index.astype(int)
frame["unmatched"] = frame.reason.fillna("").str.contains("unmatched extracted")

verdicts = {}
bundle = RUNS_DIR / f"judge_{JUDGE}_on_{EXTRACTION}" / f"judge_{JUDGE}_on_{EXTRACTION}"
for path in glob.glob(str(bundle / "verdicts/*.json")):
    paper = json.loads(Path(path).read_text())
    for v in paper["verdicts"]:
        if v.get("parsed_ok"):
            verdicts[(paper["doi"], v["extracted_index"])] = v

# A candidate three independent judges vouch for is a safer bet than one only our judge liked.
# Showing the count lets a reviewer spend their time on the contested ones.
seconded = {}
for other in ALL_JUDGES:
    d = RUNS_DIR / f"judge_{other}_on_{EXTRACTION}" / f"judge_{other}_on_{EXTRACTION}"
    for path in glob.glob(str(d / "verdicts/*.json")):
        paper = json.loads(Path(path).read_text())
        for v in paper["verdicts"]:
            if v.get("parsed_ok") and v["verdict"] == "correct":
                key = (paper["doi"], v["extracted_index"])
                seconded[key] = seconded.get(key, 0) + 1

records = {}
for path in glob.glob(str(RUNS_DIR / f"extract_{EXTRACTION}/extract_{EXTRACTION}_n4_r1"
                          / "extractions/*.json")):
    paper = json.loads(Path(path).read_text())
    for i, record in enumerate(paper["records"]):
        records[(paper["doi"], i)] = record

texts, titles = {}, {}
for path in glob.glob(str(data_path("curated_data_markdown_by_doi") / "*.md")):
    doi = Path(path).stem.replace("@", "/")
    body = Path(path).read_text(encoding="utf-8")
    parts = re.split(r"^ID: ([0-9a-f-]{36})$", body, flags=re.M)
    texts[doi] = [{"id": parts[i], "text": parts[i + 1].strip()}
                  for i in range(1, len(parts), 2)]
for paper in json.loads(data_path("curated_table_final.json").read_text()):
    titles[paper["doi"]] = paper.get("title", "")

curated_rows = {}
for paper in json.loads(data_path("curated_table_final.json").read_text()):
    curated_rows[paper["doi"]] = [e["experiment_data"] for e in paper["extracted_experiments"]]

payload = {}
for row in frame[frame.unmatched].itertuples():
    key = (row.doi, row.index)
    verdict = verdicts.get(key)
    if not verdict or verdict["verdict"] != "correct":
        continue                                   # a rescue is one the judge vouched for
    record = records.get(key, {})
    entry = payload.setdefault(row.doi, {
        "title": titles.get(row.doi, ""),
        "chunks": texts.get(row.doi, []),
        "curated": [{f: c.get(f) for f in FIELDS} for c in curated_rows.get(row.doi, [])],
        "rescues": [],
    })
    entry["rescues"].append({
        "key": f"{row.doi}#{row.index}",
        "index": int(row.index),
        "values": {f: record.get(f) for f in FIELDS},
        "chunks": record.get("source_chunk_ids") or [],
        "critique": verdict.get("critique", ""),
        "judges": seconded.get(key, 1),
    })

for entry in payload.values():
    entry["rescues"].sort(key=lambda r: (r["judges"], r["index"]))   # contested ones first
total = sum(len(p["rescues"]) for p in payload.values())

page = r"""<!doctype html><html><head><meta charset="utf-8">
<title>Are these real experiments the table missed?</title>
<style>
 *{box-sizing:border-box}
 body{font:14px/1.55 -apple-system,system-ui,"Segoe UI",sans-serif;margin:0;height:100vh;
   display:flex;flex-direction:column;color:#18202a;background:#f6f7f8}
 header{padding:9px 16px;border-bottom:1px solid #d8dde2;background:#fff;display:flex;gap:12px;
   align-items:center;flex-wrap:wrap}
 h1{font-size:15px;margin:0;font-weight:650;white-space:nowrap}
 select{padding:5px 7px;font-size:13px;max-width:400px}
 .grow{flex:1} .muted{color:#6b7681;font-size:12.5px}
 button{padding:6px 11px;font-size:13px;cursor:pointer;border:1px solid #c3cbd3;background:#fff;
   border-radius:4px} button:hover{background:#eef1f4}
 button.primary{background:#0f6b6b;color:#fff;border-color:#0f6b6b}
 main{flex:1;display:flex;min-height:0}
 #text{width:44%;overflow-y:auto;padding:15px 19px;border-right:1px solid #d8dde2;background:#fff;
   font-size:12.5px;white-space:pre-wrap}
 #right{flex:1;overflow-y:auto;padding:13px 16px}
 .chunk{padding:5px 8px;border-left:3px solid transparent;margin:2px 0}
 .chunk.hit{background:#fff8d6;border-left-color:#e0a800}
 .cid{color:#b3bcc4;font-size:9.5px;display:block;user-select:none}
 mark{background:#bfe8e2;border-radius:2px}
 .card{border:1px solid #dfe4e8;border-left:4px solid #c3cbd3;border-radius:5px;padding:9px 11px;
   margin-bottom:9px;background:#fff}
 .card.real{border-left-color:#2f8f6d;background:#fbfefc}
 .card.notreal{border-left-color:#b8442f;background:#fffafa}
 .card.sel{box-shadow:0 0 0 2px #cfe6e4}
 .top{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:5px}
 .top label{display:flex;gap:4px;align-items:center;font-size:12.5px;cursor:pointer}
 .look{margin-left:auto;font-size:11.5px;color:#0f6b6b;cursor:pointer;text-decoration:underline}
 .vals{font:11.5px ui-monospace,Menlo,monospace;line-height:1.7;color:#2b353f}
 .vals b{color:#6b7681;font-weight:600}
 .badge{font:10px ui-monospace,Menlo,monospace;text-transform:uppercase;letter-spacing:.05em;
   padding:1px 6px;border-radius:2px;background:#f0e5d6;color:#8a5a1c}
 .badge.all{background:#dcefe5;color:#245f48}
 .why{font-size:12px;color:#5a6470;margin-top:6px;padding-top:6px;border-top:1px dotted #dfe4e8}
 details{margin-bottom:10px}
 summary{cursor:pointer;font-size:12.5px;color:#3d5666}
 table.cur{border-collapse:collapse;font:11px ui-monospace,Menlo,monospace;margin-top:6px;
   display:block;overflow-x:auto;max-width:100%}
 table.cur th{text-align:left;color:#6b7681;padding:2px 7px;border-bottom:1px solid #e4e8ec;
   white-space:nowrap}
 table.cur td{padding:2px 7px;border-bottom:1px solid #f2f4f6;white-space:nowrap}
 .hint{background:#eef4f7;border:1px solid #cfdde6;border-radius:4px;padding:8px 11px;
   margin-bottom:10px;font-size:12px;color:#3d5666}
 footer{padding:7px 16px;border-top:1px solid #d8dde2;background:#fff;display:flex;gap:10px;
   align-items:center;font-size:13px;flex-wrap:wrap}
 #note{flex:1;min-width:200px;padding:5px 7px;font-size:13px;border:1px solid #c3cbd3;
   border-radius:4px}
</style></head><body>
<header>
  <h1>Are these real experiments the table missed?</h1>
  <select id="pick"></select>
  <span class="muted" id="stat"></span>
  <span class="grow"></span>
  <span class="muted" id="progress"></span>
  <button class="primary" onclick="save()">Download decisions</button>
</header>
<main><div id="text"></div><div id="right"></div></main>
<footer>
  <span class="muted">Note for this paper:</span>
  <input id="note" placeholder="optional">
</footer>
<script>
const DATA = __DATA__;
const FIELDS = __FIELDS__;
const STORE = 'rescueReview.v1';
let state = (() => { try { return JSON.parse(localStorage.getItem(STORE)) || {answers:{},notes:{}}; }
                     catch(e){ return {answers:{},notes:{}}; } })();
let current = null;

const dois = Object.keys(DATA).sort();
const pick = document.getElementById('pick');
dois.forEach(d => pick.add(new Option(d + '  (' + DATA[d].rescues.length + ')', d)));

function esc(s){ return String(s).replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function total(){
  let n = 0, all = 0;
  dois.forEach(d => DATA[d].rescues.forEach(r => { all++; if (state.answers[r.key]) n++; }));
  document.getElementById('progress').textContent = n + ' of ' + all + ' decided';
}
function persist(){ try { localStorage.setItem(STORE, JSON.stringify(state)); } catch(e){} total(); }

function clearMarks(){
  document.querySelectorAll('#text mark').forEach(m =>
    m.parentNode.replaceChild(document.createTextNode(m.textContent), m));
  document.getElementById('text').normalize();
}
function highlight(rec){
  clearMarks();
  document.querySelectorAll('.chunk').forEach(c => c.classList.remove('hit'));
  (rec.chunks||[]).forEach(id => {
    const el = document.getElementById('k_' + id);
    if (el) el.classList.add('hit');
  });
  const terms = FIELDS.filter(f => f !== 'catalyst' && f !== 'solvent' && f !== 'product')
    .map(f => rec.values[f]).filter(v => v !== null && v !== undefined && String(v).length > 1)
    .map(v => String(v).replace(/[.*+?^${}()|[\]\\]/g,'\\$&'));
  if (terms.length){
    const re = new RegExp('(?<![\\w.])(' + terms.join('|') + ')(?![\\w.])','g');
    const walker = document.createTreeWalker(document.getElementById('text'), NodeFilter.SHOW_TEXT);
    const hits = [];
    while (walker.nextNode()){
      const node = walker.currentNode;
      if (node.parentElement.closest('mark')) continue;
      re.lastIndex = 0;
      if (re.test(node.nodeValue)) hits.push(node);
    }
    hits.forEach(node => {
      const span = document.createElement('span');
      re.lastIndex = 0;
      span.innerHTML = esc(node.nodeValue).replace(re, '<mark>$1</mark>');
      node.parentNode.replaceChild(span, node);
    });
  }
  const first = document.querySelector('.chunk.hit') || document.querySelector('#text mark');
  if (first) first.scrollIntoView({block:'center', behavior:'smooth'});
}

function card(rec){
  const box = document.createElement('div');
  const answer = state.answers[rec.key];
  box.className = 'card' + (answer === 'real' ? ' real' : answer === 'notreal' ? ' notreal' : '');

  const top = document.createElement('div');
  top.className = 'top';
  [['real','a real experiment the table missed'],
   ['notreal','not a real experiment'],
   ['unsure','not sure']].forEach(([value,label]) => {
    const l = document.createElement('label');
    const r = document.createElement('input');
    r.type = 'radio'; r.name = rec.key; r.value = value; r.checked = answer === value;
    r.addEventListener('change', () => {
      state.answers[rec.key] = value;
      box.className = 'card' + (value === 'real' ? ' real' : value === 'notreal' ? ' notreal' : '');
      persist();
    });
    l.appendChild(r); l.appendChild(document.createTextNode(label));
    top.appendChild(l);
  });
  const tag = document.createElement('span');
  tag.className = 'badge' + (rec.judges === 3 ? ' all' : '');
  tag.textContent = rec.judges + ' of 3 judges call this real';
  top.appendChild(tag);

  const look = document.createElement('span');
  look.className = 'look'; look.textContent = 'find in text';
  look.addEventListener('click', () => {
    document.querySelectorAll('.card.sel').forEach(e => e.classList.remove('sel'));
    box.classList.add('sel'); highlight(rec);
  });
  top.appendChild(look);
  box.appendChild(top);

  const vals = document.createElement('div');
  vals.className = 'vals';
  vals.innerHTML = Object.entries(rec.values)
    .filter(([k,v]) => v !== null && v !== undefined)
    .map(([k,v]) => '<b>' + esc(k) + '</b> ' + esc(v)).join(' &middot; ');
  box.appendChild(vals);

  if (rec.critique){
    const why = document.createElement('div');
    why.className = 'why';
    why.textContent = 'Judge: ' + rec.critique;
    box.appendChild(why);
  }
  return box;
}

function show(doi){
  current = doi;
  const p = DATA[doi];
  document.getElementById('text').innerHTML = p.chunks.map(c =>
    '<div class="chunk" id="k_' + c.id + '"><span class="cid">' + c.id + '</span>'
    + esc(c.text) + '</div>').join('');

  const box = document.getElementById('right');
  box.innerHTML = '';
  const hint = document.createElement('div');
  hint.className = 'hint';
  hint.textContent = 'Each record below was extracted from this paper, and our curated table has '
    + 'nothing to compare it against. If it describes a real experiment the paper reports, our '
    + 'table simply missed it. If it does not, the extraction invented it. Your answer decides '
    + 'which of these count against the graders.';
  box.appendChild(hint);

  const det = document.createElement('details');
  const sum = document.createElement('summary');
  sum.textContent = 'what our curated table already holds for this paper ('
                    + p.curated.length + ' experiments)';
  det.appendChild(sum);
  const scroll = document.createElement('div');
  const t = document.createElement('table');
  t.className = 'cur';
  const shown = FIELDS.filter(f => p.curated.some(c => c[f] !== null && c[f] !== undefined));
  const head = document.createElement('tr');
  shown.forEach(f => { const th = document.createElement('th');
    th.textContent = f.replace('_percent','').replace('_c','').replace('_min','');
    head.appendChild(th); });
  t.appendChild(head);
  p.curated.forEach(c => {
    const tr = document.createElement('tr');
    shown.forEach(f => { const td = document.createElement('td');
      td.textContent = c[f] === null || c[f] === undefined ? '—' : c[f]; tr.appendChild(td); });
    t.appendChild(tr);
  });
  scroll.appendChild(t); det.appendChild(scroll); box.appendChild(det);

  p.rescues.forEach(r => box.appendChild(card(r)));
  document.getElementById('stat').textContent = p.rescues.length + ' to decide';
  document.getElementById('note').value = state.notes[doi] || '';
  document.getElementById('text').scrollTop = 0;
  total();
}

document.getElementById('note').addEventListener('input', e => {
  state.notes[current] = e.target.value; persist();
});
pick.addEventListener('change', () => show(pick.value));

function save(){
  const out = {generated: new Date().toISOString(), decisions: [], notes: state.notes};
  dois.forEach(d => DATA[d].rescues.forEach(r => {
    out.decisions.push({key: r.key, doi: d, index: r.index,
                        answer: state.answers[r.key] || null,
                        catalyst: r.values.catalyst, temperature_c: r.values.temperature_c,
                        reaction_time_min: r.values.reaction_time_min});
  }));
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 2)], {type:'application/json'}));
  a.download = 'rescue_decisions.json';
  a.click();
}

show(dois[0]);
total();
</script></body></html>
"""

page = page.replace("__DATA__", json.dumps(payload)).replace("__FIELDS__", json.dumps(FIELDS))
out = ARTIFACTS / "rescue_review.html"
out.write_text(page, encoding="utf-8")

print(f"wrote {out}  ({out.stat().st_size // 1024} KB)")
print(f"extraction {EXTRACTION}, judge {JUDGE}")
print(f"records with no counterpart that the judge vouched for: {total}")
print(f"across {len(payload)} papers")
