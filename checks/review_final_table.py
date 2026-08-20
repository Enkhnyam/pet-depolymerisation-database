import glob
import json
import re
import sys
from pathlib import Path

from markdown_it import MarkdownIt

sys.path.insert(0, str(Path(__file__).parent))
from _setup import ARTIFACTS, data_path, curated_table
from review_curation import FIELDS, clean_name, close_enough, to_chunks

FINAL = "curated_table_final.json"

final = json.loads(data_path(FINAL).read_text())
before = {p["doi"].lower(): [e["experiment_data"] for e in p["extracted_experiments"]]
          for p in json.loads(data_path(curated_table).read_text())}

texts = {}
for path in glob.glob(str(data_path("curated_data_markdown_by_doi") / "*.md")):
    texts[Path(path).stem.replace("@", "/").lower()] = Path(path).read_text(encoding="utf-8")


def was_there(doi, row):
    """Was this experiment already in the table before the review round?"""
    for old in before.get(doi, []):
        if clean_name(old.get("catalyst")) != clean_name(row.get("catalyst")):
            continue
        if all(close_enough(old.get(f), row.get(f))
               for f in ("temperature_c", "reaction_time_min", "yield_percent",
                         "selectivity_percent", "conversion_percent")):
            return True
    return False


payload = {}
for paper in final:
    doi = paper["doi"].lower()
    rows = []
    for i, entry in enumerate(paper["extracted_experiments"]):
        data = entry["experiment_data"]
        rows.append({
            "n": i + 1,
            "values": {f: data.get(f) for f in FIELDS if data.get(f) is not None},
            "chunks": data.get("source_chunk_ids") or [],
            "isNew": not was_there(doi, data),
        })
    payload[paper["doi"]] = {
        "title": paper.get("title", ""),
        "chunks": to_chunks(texts.get(doi, "")),
        "rows": rows,
    }

totals = {"papers": len(payload),
          "rows": sum(len(p["rows"]) for p in payload.values()),
          "added": sum(1 for p in payload.values() for r in p["rows"] if r["isNew"]),
          "noProvenance": sum(1 for p in payload.values() for r in p["rows"] if not r["chunks"])}

page = r"""<!doctype html><html><head><meta charset="utf-8">
<title>Check the final curated table</title>
<style>
 *{box-sizing:border-box}
 body{font:14px/1.55 -apple-system,system-ui,"Segoe UI",sans-serif;margin:0;height:100vh;
   display:flex;flex-direction:column;color:#18202a;background:#f6f7f8}
 header{padding:9px 16px;border-bottom:1px solid #d8dde2;background:#fff;
   display:flex;gap:12px;align-items:center;flex-wrap:wrap}
 header h1{font-size:15px;margin:0;white-space:nowrap;font-weight:650}
 select{padding:5px 7px;font-size:13px;max-width:420px}
 .grow{flex:1} .muted{color:#6b7681;font-size:12.5px}
 button{padding:6px 11px;font-size:13px;cursor:pointer;border:1px solid #c3cbd3;
   background:#fff;border-radius:4px}
 button.primary{background:#0f6b6b;color:#fff;border-color:#0f6b6b}
 main{flex:1;display:flex;min-height:0}
 #text{width:50%;overflow-y:auto;padding:15px 19px;border-right:1px solid #d8dde2;
   background:#fff;font-size:12.5px}
 #rows{flex:1;overflow-y:auto;padding:13px 16px}
 .chunk{padding:5px 8px;border-left:3px solid transparent;margin:2px 0}
 .chunk table{border-collapse:collapse;margin:7px 0;font-size:11px;display:block;
   overflow-x:auto;max-width:100%}
 .chunk th,.chunk td{border:1px solid #ccc;padding:3px 7px;text-align:left;white-space:nowrap}
 .chunk th{background:#eee}
 .chunk p{margin:4px 0}
 .chunk.hit{background:#fff8d6;border-left-color:#e0a800}
 .cid{color:#b3bcc4;font-size:9.5px;user-select:none;display:block}
 mark.val{background:#bfe8e2;border-radius:2px;padding:0 1px}
 mark.cat{background:#ffd9a8;border-radius:2px;padding:0 1px;font-weight:600}
 .row{border:1px solid #dfe4e8;border-left:4px solid #c3cbd3;border-radius:4px;
   padding:7px 10px;margin-bottom:7px;background:#fff;cursor:pointer}
 .row:hover{border-color:#0f6b6b}
 .row.sel{box-shadow:0 0 0 2px #cfe6e4;border-color:#0f6b6b}
 .row.new{border-left-color:#c9721f;background:#fffaf4}
 .row.ok{border-left-color:#3f9070}
 .top{display:flex;gap:7px;align-items:center;margin-bottom:3px;flex-wrap:wrap}
 .n{font:11px ui-monospace,Menlo,monospace;color:#8b96a1}
 .tag{font:10px ui-monospace,Menlo,monospace;text-transform:uppercase;letter-spacing:.05em;
   padding:1px 5px;border-radius:2px;background:#e8edf1;color:#4a5763}
 .tag.new{background:#f7e6d4;color:#8a4d12}
 .tag.noprov{background:#f2e3e3;color:#8a2f2f}
 .vals{font:11.5px ui-monospace,Menlo,monospace;line-height:1.75;color:#2b353f}
 .vals b{color:#6b7681;font-weight:600}
 .hint{background:#eef4f7;border:1px solid #cfdde6;border-radius:4px;padding:7px 10px;
   margin-bottom:9px;font-size:12px;color:#3d5666}
 footer{padding:7px 16px;border-top:1px solid #d8dde2;background:#fff;display:flex;
   gap:10px;align-items:center;flex-wrap:wrap;font-size:13px}
 #note{flex:1;min-width:200px;padding:5px 7px;font-size:13px;border:1px solid #c3cbd3;border-radius:4px}
</style></head><body>
<header>
  <h1>Check the final curated table</h1>
  <select id="pick"></select>
  <span class="muted" id="stat"></span>
  <span class="grow"></span>
  <label class="muted"><input type="checkbox" id="onlyNew"> only rows added this round</label>
  <span class="muted" id="progress"></span>
  <button class="primary" onclick="save()">Download notes</button>
</header>
<main><div id="text"></div><div id="rows"></div></main>
<footer>
  <label class="muted"><input type="checkbox" id="done"> I have checked this paper</label>
  <input id="note" placeholder="note (optional)">
</footer>
<script>
const DATA = __DATA__;
const TOTALS = __TOTALS__;
const STORE = 'finalTableCheck.v1';
let state = (() => { try { return JSON.parse(localStorage.getItem(STORE)) || {}; }
                     catch (e) { return {}; } })();
let current = null;

const dois = Object.keys(DATA).sort();
const pick = document.getElementById('pick');
dois.forEach(d => {
  const p = DATA[d];
  const added = p.rows.filter(r => r.isNew).length;
  pick.add(new Option(d + '   (' + p.rows.length + ' rows' + (added ? ', ' + added + ' new' : '') + ')', d));
});

function esc(s){ return String(s).replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

function progress(){
  const done = dois.filter(d => (state[d] || {}).done).length;
  document.getElementById('progress').textContent = done + ' of ' + dois.length + ' papers checked';
}
function persist(){ try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (e) {} progress(); }

function clearMarks(){
  document.querySelectorAll('#text mark').forEach(m =>
    m.parentNode.replaceChild(document.createTextNode(m.textContent), m));
  document.getElementById('text').normalize();
}
function terms(values){
  const out = [];
  for (const [k, v] of Object.entries(values)){
    if (k === 'catalyst' || k === 'solvent') continue;
    const s = String(v);
    if (s.length >= 2) out.push(s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  }
  return out;
}
function paint(list, cls){
  if (!list.length) return;
  const re = new RegExp('(?<![\\w.])(' + list.join('|') + ')(?![\\w.])', 'g');
  const walker = document.createTreeWalker(document.getElementById('text'), NodeFilter.SHOW_TEXT);
  const targets = [];
  while (walker.nextNode()){
    const node = walker.currentNode;
    if (node.parentElement.closest('mark')) continue;
    re.lastIndex = 0;
    if (re.test(node.nodeValue)) targets.push(node);
  }
  targets.forEach(node => {
    const span = document.createElement('span');
    re.lastIndex = 0;
    span.innerHTML = esc(node.nodeValue).replace(re, '<mark class="' + cls + '">$1</mark>');
    node.parentNode.replaceChild(span, node);
  });
}
function highlight(row){
  clearMarks();
  document.querySelectorAll('.chunk').forEach(c => c.classList.remove('hit'));
  row.chunks.forEach(id => {
    const el = document.getElementById('k_' + id);
    if (el) el.classList.add('hit');
  });
  const cat = String(row.values.catalyst || '').trim();
  if (cat.length >= 3) paint([cat.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')], 'cat');
  paint(terms(row.values), 'val');
  const first = document.querySelector('.chunk.hit') || document.querySelector('#text mark');
  if (first) first.scrollIntoView({block:'center', behavior:'smooth'});
}

function show(doi){
  current = doi;
  const paper = DATA[doi];
  document.getElementById('text').innerHTML = paper.chunks.map(c =>
    '<div class="chunk" id="k_' + c.id + '"><span class="cid">' + c.id + '</span>' + c.html
    + '</div>').join('');

  const box = document.getElementById('rows');
  box.innerHTML = '';
  const hint = document.createElement('div');
  hint.className = 'hint';
  hint.textContent = 'Orange rows were added during the review round; the rest were already in the '
    + 'table. A row marked "no provenance" came from a published review rather than our own '
    + 'extraction, so it carries no link into the text. Click a row to highlight its values.';
  box.appendChild(hint);

  const onlyNew = document.getElementById('onlyNew').checked;
  paper.rows.filter(r => !onlyNew || r.isNew).forEach(row => {
    const el = document.createElement('div');
    el.className = 'row ' + (row.isNew ? 'new' : 'ok');
    const top = document.createElement('div');
    top.className = 'top';
    const n = document.createElement('span'); n.className = 'n'; n.textContent = '#' + row.n;
    top.appendChild(n);
    if (row.isNew){
      const t = document.createElement('span'); t.className = 'tag new';
      t.textContent = 'added this round'; top.appendChild(t);
    }
    if (!row.chunks.length){
      const t = document.createElement('span'); t.className = 'tag noprov';
      t.textContent = 'no provenance'; top.appendChild(t);
    }
    el.appendChild(top);
    const vals = document.createElement('div');
    vals.className = 'vals';
    vals.innerHTML = Object.entries(row.values)
      .map(([k, v]) => '<b>' + esc(k) + '</b> ' + esc(v)).join(' &middot; ');
    el.appendChild(vals);
    el.addEventListener('click', () => {
      document.querySelectorAll('.row.sel').forEach(x => x.classList.remove('sel'));
      el.classList.add('sel');
      highlight(row);
    });
    box.appendChild(el);
  });

  const added = paper.rows.filter(r => r.isNew).length;
  const noprov = paper.rows.filter(r => !r.chunks.length).length;
  document.getElementById('stat').textContent =
    paper.rows.length + ' rows · ' + added + ' added · ' + noprov + ' without provenance';
  const saved = state[doi] || {};
  document.getElementById('done').checked = !!saved.done;
  document.getElementById('note').value = saved.note || '';
  document.getElementById('text').scrollTop = 0;
}

document.getElementById('done').addEventListener('change', e => {
  state[current] = Object.assign({}, state[current], {done: e.target.checked}); persist();
});
document.getElementById('note').addEventListener('input', e => {
  state[current] = Object.assign({}, state[current], {note: e.target.value}); persist();
});
document.getElementById('onlyNew').addEventListener('change', () => show(current));
pick.addEventListener('change', () => show(pick.value));

function save(){
  const out = {generated: new Date().toISOString(), totals: TOTALS,
               papers: dois.map(d => ({doi: d, rows: DATA[d].rows.length,
                 added: DATA[d].rows.filter(r => r.isNew).length,
                 checked: !!(state[d] || {}).done, note: (state[d] || {}).note || ''}))};
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 2)], {type:'application/json'}));
  a.download = 'final_table_check.json';
  a.click();
}

show(dois[0]);
progress();
</script></body></html>
"""

page = page.replace("__DATA__", json.dumps(payload)).replace("__TOTALS__", json.dumps(totals))
out = ARTIFACTS / "final_table_check.html"
out.write_text(page, encoding="utf-8")

print(f"wrote {out}  ({out.stat().st_size // 1024} KB)")
print(f"papers                      {totals['papers']}")
print(f"experiments                 {totals['rows']}")
print(f"  added during the review   {totals['added']}")
print(f"  without provenance        {totals['noProvenance']}")
print(f"papers containing added rows {sum(1 for p in payload.values() if any(r['isNew'] for r in p['rows']))}")
