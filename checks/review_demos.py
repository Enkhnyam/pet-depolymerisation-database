"""Review page for the worked examples that will be shown to the extractor.

These records become the demo answers verbatim, so an error here is taught to the model on every
paper of the mass run. The page puts the paper on the left and the draft records on the right,
every field editable, and exports the confirmed result in the shape
curated_data_json_by_doi.json expects.
"""
import glob
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _setup import ARTIFACTS, RUNS_DIR, data_path

FIELDS = ["catalyst", "solvent", "product", "temperature_c", "reaction_time_min",
          "catalyst_amount_g", "PET_amount_g", "solvent_amount_g",
          "yield_percent", "selectivity_percent", "conversion_percent", "pressure_atm"]
NUMERIC = {f for f in FIELDS if f.endswith(("_c", "_min", "_g", "_percent", "_atm"))}

DRAFTS = "demo_drafts/demo_drafts_n4_r1"
TEXTS = "demo_candidates_markdown"
ROUTES = {
    "10.1016/j.polymdegradstab.2023.110353": "glycolysis",
    "10.1016/j.eehl.2025.100139": "methanolysis",
    "10.1016/j.jece.2025.119272": "hydrolysis",
    "10.1016/j.eurpolymj.2021.110441": "aminolysis",
    "10.1016/j.ceja.2026.101322": "deep eutectic solvent",
}


def chunks_of(text):
    parts = re.split(r"^ID: ([0-9a-f-]{36})$", text, flags=re.M)
    return [{"id": parts[i], "text": parts[i + 1].strip()}
            for i in range(1, len(parts), 2)]


payload = {}
for path in sorted(glob.glob(str(RUNS_DIR / DRAFTS / "extractions/*.json"))):
    paper = json.loads(Path(path).read_text())
    doi = paper["doi"]
    md = data_path(TEXTS) / (doi.replace("/", "@") + ".md")
    if not md.exists():
        continue
    body = md.read_text(encoding="utf-8")
    parsed = chunks_of(body)
    title = next((c["text"].split("\n")[0] for c in parsed if c["text"]), doi)
    payload[doi] = {
        "route": ROUTES.get(doi, "?"),
        "title": title,
        "chunks": parsed,
        "records": [{"n": i + 1,
                     "values": {f: r.get(f) for f in FIELDS},
                     "chunks": r.get("source_chunk_ids") or []}
                    for i, r in enumerate(paper["records"])],
    }

page = r"""<!doctype html><html><head><meta charset="utf-8">
<title>Check the worked examples</title>
<style>
 *{box-sizing:border-box}
 body{font:14px/1.55 -apple-system,system-ui,"Segoe UI",sans-serif;margin:0;height:100vh;
   display:flex;flex-direction:column;color:#18202a;background:#f6f7f8}
 header{padding:9px 16px;border-bottom:1px solid #d8dde2;background:#fff;display:flex;
   gap:12px;align-items:center;flex-wrap:wrap}
 h1{font-size:15px;margin:0;font-weight:650;white-space:nowrap}
 select{padding:5px 7px;font-size:13px;max-width:420px}
 .grow{flex:1} .muted{color:#6b7681;font-size:12.5px}
 button{padding:6px 11px;font-size:13px;cursor:pointer;border:1px solid #c3cbd3;background:#fff;
   border-radius:4px} button:hover{background:#eef1f4}
 button.primary{background:#0f6b6b;color:#fff;border-color:#0f6b6b}
 main{flex:1;display:flex;min-height:0}
 #text{width:46%;overflow-y:auto;padding:15px 19px;border-right:1px solid #d8dde2;background:#fff;
   font-size:12.5px;white-space:pre-wrap}
 #cards{flex:1;overflow-y:auto;padding:13px 16px}
 .chunk{padding:5px 8px;border-left:3px solid transparent;margin:2px 0}
 .chunk.hit{background:#fff8d6;border-left-color:#e0a800}
 .cid{color:#b3bcc4;font-size:9.5px;display:block;user-select:none}
 mark{background:#bfe8e2;border-radius:2px}
 .card{border:1px solid #dfe4e8;border-left:4px solid #3f9070;border-radius:5px;padding:9px 11px;
   margin-bottom:9px;background:#fff}
 .card.drop{border-left-color:#b8442f;background:#fffafa;opacity:.6}
 .card.sel{box-shadow:0 0 0 2px #cfe6e4}
 .top{display:flex;gap:9px;align-items:center;margin-bottom:6px;flex-wrap:wrap}
 .n{font:11px ui-monospace,Menlo,monospace;color:#8b96a1}
 .look{margin-left:auto;font-size:11.5px;color:#0f6b6b;cursor:pointer;text-decoration:underline}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:5px}
 label.f{display:flex;flex-direction:column;gap:1px;font:10.5px ui-monospace,Menlo,monospace;
   color:#6b7681}
 label.f input{padding:3px 5px;font:11.5px ui-monospace,Menlo,monospace;border:1px solid #c8d0d8;
   border-radius:3px;width:100%}
 label.f input.empty{background:#fdf3e7;border-color:#e8c89b}
 .hint{background:#eef4f7;border:1px solid #cfdde6;border-radius:4px;padding:8px 11px;
   margin-bottom:10px;font-size:12px;color:#3d5666}
 footer{padding:7px 16px;border-top:1px solid #d8dde2;background:#fff;display:flex;gap:10px;
   align-items:center;font-size:13px;flex-wrap:wrap}
 #note{flex:1;min-width:200px;padding:5px 7px;font-size:13px;border:1px solid #c3cbd3;
   border-radius:4px}
</style></head><body>
<header>
  <h1>Check the worked examples</h1>
  <select id="pick"></select>
  <span class="muted" id="stat"></span>
  <span class="grow"></span>
  <span class="muted" id="progress"></span>
  <button class="primary" onclick="save()">Download confirmed examples</button>
</header>
<main><div id="text"></div><div id="cards"></div></main>
<footer>
  <label class="muted"><input type="checkbox" id="done"> this paper is checked</label>
  <input id="note" placeholder="note for this paper (optional)">
</footer>
<script>
const DATA = __DATA__;
const FIELDS = __FIELDS__;
const NUMERIC = __NUMERIC__;
const STORE = 'demoReview.v1';
let state = (() => { try { return JSON.parse(localStorage.getItem(STORE)) || {}; }
                     catch(e){ return {}; } })();
let current = null;

const dois = Object.keys(DATA);
const pick = document.getElementById('pick');
dois.forEach(d => pick.add(new Option(DATA[d].route + ' — ' + d, d)));

function esc(s){ return String(s).replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

function paperState(doi){
  if (!state[doi]) state[doi] = {records:{}, done:false, note:''};
  return state[doi];
}
function recState(doi, n){
  const p = paperState(doi);
  if (!p.records[n]) p.records[n] = {keep:true, values:{}};
  return p.records[n];
}
function persist(){
  try { localStorage.setItem(STORE, JSON.stringify(state)); } catch(e){}
  const n = dois.filter(d => (state[d]||{}).done).length;
  document.getElementById('progress').textContent = n + ' of ' + dois.length + ' papers checked';
}

function valueOf(doi, rec, field){
  const s = recState(doi, rec.n);
  return (field in s.values) ? s.values[field] : rec.values[field];
}

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
  const terms = FIELDS.filter(f => NUMERIC.includes(f))
    .map(f => valueOf(current, rec, f)).filter(v => v !== null && v !== undefined && String(v).length > 1)
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

function card(doi, rec){
  const s = recState(doi, rec.n);
  const box = document.createElement('div');
  box.className = 'card' + (s.keep ? '' : ' drop');

  const top = document.createElement('div');
  top.className = 'top';
  const keep = document.createElement('label');
  const cb = document.createElement('input');
  cb.type = 'checkbox'; cb.checked = s.keep;
  cb.addEventListener('change', () => {
    s.keep = cb.checked; box.classList.toggle('drop', !cb.checked); persist();
  });
  keep.appendChild(cb); keep.appendChild(document.createTextNode(' keep'));
  top.appendChild(keep);
  const n = document.createElement('span'); n.className='n'; n.textContent='#'+rec.n;
  top.appendChild(n);
  const look = document.createElement('span');
  look.className='look'; look.textContent='find in text';
  look.addEventListener('click', () => {
    document.querySelectorAll('.card.sel').forEach(e=>e.classList.remove('sel'));
    box.classList.add('sel'); highlight(rec);
  });
  top.appendChild(look);
  box.appendChild(top);

  const grid = document.createElement('div');
  grid.className = 'grid';
  FIELDS.forEach(f => {
    const lab = document.createElement('label');
    lab.className = 'f'; lab.textContent = f;
    const input = document.createElement('input');
    const v = valueOf(doi, rec, f);
    input.value = (v === null || v === undefined) ? '' : v;
    if (input.value === '') input.classList.add('empty');
    input.addEventListener('input', () => {
      const raw = input.value.trim();
      s.values[f] = raw === '' ? null
        : (NUMERIC.includes(f) && !isNaN(Number(raw)) ? Number(raw) : raw);
      input.classList.toggle('empty', raw === '');
      persist();
    });
    lab.appendChild(input);
    grid.appendChild(lab);
  });
  box.appendChild(grid);
  return box;
}

function show(doi){
  current = doi;
  const p = DATA[doi];
  document.getElementById('text').innerHTML = p.chunks.map(c =>
    '<div class="chunk" id="k_' + c.id + '"><span class="cid">' + c.id + '</span>'
    + esc(c.text) + '</div>').join('');

  const box = document.getElementById('cards');
  box.innerHTML = '';
  const hint = document.createElement('div');
  hint.className = 'hint';
  hint.textContent = 'These records become the worked examples the extractor is shown, copied '
    + 'exactly as written here. An error is taught to the model on every paper of the mass run, so '
    + 'check every field. Orange boxes are empty values — some are correct, some are misses. '
    + 'Untick "keep" to drop a record.';
  box.appendChild(hint);
  p.records.forEach(r => box.appendChild(card(doi, r)));

  document.getElementById('stat').textContent = p.records.length + ' draft records';
  const st = paperState(doi);
  document.getElementById('done').checked = !!st.done;
  document.getElementById('note').value = st.note || '';
  document.getElementById('text').scrollTop = 0;
  persist();
}

document.getElementById('done').addEventListener('change', e => {
  paperState(current).done = e.target.checked; persist();
});
document.getElementById('note').addEventListener('input', e => {
  paperState(current).note = e.target.value; persist();
});
pick.addEventListener('change', () => show(pick.value));

function save(){
  const out = [];
  dois.forEach(doi => {
    const p = DATA[doi];
    const kept = p.records.filter(r => recState(doi, r.n).keep).map(r => {
      const values = {};
      FIELDS.forEach(f => { values[f] = valueOf(doi, r, f); });
      values.source_chunk_ids = r.chunks || [];
      return {experiment_data: values};
    });
    out.push({doi: doi, title: p.title, route: p.route,
              checked: !!paperState(doi).done, note: paperState(doi).note || '',
              full_text: p.chunks.map(c => 'ID: ' + c.id + '\n' + c.text).join('\n\n'),
              extracted_experiments: kept});
  });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 2)],
                                        {type:'application/json'}));
  a.download = 'confirmed_examples.json';
  a.click();
}

show(dois[0]);
persist();
</script></body></html>
"""

page = (page.replace("__DATA__", json.dumps(payload))
            .replace("__FIELDS__", json.dumps(FIELDS))
            .replace("__NUMERIC__", json.dumps(sorted(NUMERIC))))
out = ARTIFACTS / "demo_review.html"
out.write_text(page, encoding="utf-8")

print(f"wrote {out}  ({out.stat().st_size // 1024} KB)")
for doi, paper in payload.items():
    empty = sum(1 for r in paper["records"] for f in FIELDS if r["values"].get(f) is None)
    print(f"  {paper['route']:22s} {len(paper['records']):3d} records, "
          f"{empty} empty fields  {doi}")
