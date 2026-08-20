import glob
import html
import re
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _setup import ARTIFACTS, RUNS_DIR, data_path, judge_run
from _curation import extracted_records, missing_experiments
from markdown_it import MarkdownIt

renderer = MarkdownIt("commonmark").enable("table")

FIELDS = ["catalyst", "solvent", "temperature_c", "reaction_time_min", "catalyst_amount_g",
          "PET_amount_g", "solvent_amount_g", "yield_percent", "selectivity_percent",
          "conversion_percent", "pressure_atm"]

records = extracted_records()
candidates = missing_experiments()

reasons = {}
for path in glob.glob(str(RUNS_DIR / judge_run / "verdicts/*.json")):
    paper = json.loads(Path(path).read_text())
    for verdict in paper["verdicts"]:
        reasons[(paper["doi"], verdict["extracted_index"])] = verdict.get("critique", "")

papers = json.loads(data_path("curated_data_json_by_doi.json").read_text())
titles = {paper["doi"]: paper.get("title", "") for paper in papers}

texts = {}
for path in glob.glob(str(data_path("curated_data_markdown_by_doi") / "*.md")):
    doi = Path(path).stem.replace("@", "/")
    texts[doi] = Path(path).read_text(encoding="utf-8")

by_paper = {}
for row in candidates.itertuples():
    by_paper.setdefault(row.doi, []).append(row)

def to_chunks(text):
    parts = re.split(r"^ID: ([0-9a-f-]{36})$", text, flags=re.M)
    chunks = []
    for i in range(1, len(parts), 2):
        chunks.append({"id": parts[i], "html": renderer.render(parts[i + 1])})
    return chunks


payload = {}
for doi, rows in by_paper.items():
    payload[doi] = {
        "title": titles.get(doi, ""),
        "chunks": to_chunks(texts.get(doi, "")),
        "records": [{
            "key": f"{doi}#{row.extracted_index}",
            "index": row.extracted_index,
            "values": {field: records[(doi, row.extracted_index)].get(field)
                       for field in FIELDS
                       if records[(doi, row.extracted_index)].get(field) is not None},
            "reason": reasons.get((doi, row.extracted_index), ""),
            "chunks": records[(doi, row.extracted_index)].get("source_chunk_ids") or [],
        } for row in sorted(rows, key=lambda r: r.extracted_index)],
    }

page = """<!doctype html><html><head><meta charset="utf-8"><title>Experiments to add</title>
<style>
 *{box-sizing:border-box} body{font:14px/1.5 -apple-system,system-ui,sans-serif;margin:0;height:100vh;
   display:flex;flex-direction:column;color:#1a1a1a}
 header{padding:12px 20px;border-bottom:1px solid #ddd;display:flex;gap:16px;align-items:center}
 header h1{font-size:16px;margin:0;white-space:nowrap}
 select{padding:5px;font-size:14px;max-width:420px}
 .grow{flex:1} .count{color:#666;font-size:13px}
 button{padding:7px 14px;font-size:14px;cursor:pointer}
 main{flex:1;display:flex;min-height:0}
 #text{width:52%;overflow-y:auto;padding:18px 22px;border-right:1px solid #ddd;
   background:#fcfcfc;font-size:12.5px}
 .chunk{padding:6px 9px;border-left:3px solid transparent;margin:2px 0}
 .chunk table{border-collapse:collapse;margin:8px 0;font-size:11px;width:auto}
 .chunk th,.chunk td{border:1px solid #ccc;padding:3px 7px;text-align:left;white-space:nowrap}
 .chunk th{background:#eee}
 .chunk p{margin:5px 0} .chunk h1,.chunk h2,.chunk h3{font-size:13px;margin:8px 0 4px}
 .chunk.hit{background:#fff8d6;border-left-color:#e0a800}
 .cid{color:#aaa;font-size:10px;user-select:none;display:block}
 #text mark{background:#ffe066}
 #cards{flex:1;overflow-y:auto;padding:18px 22px}
 .title{color:#666;font-size:13px;margin-bottom:12px}
 .card{border:1px solid #e0e0e0;border-left:4px solid #bbb;border-radius:6px;padding:11px 13px;margin-bottom:12px}
 .card.yes{border-left-color:#2e9e5b;background:#fbfefc}
 .card.no{border-left-color:#c23b3b;background:#fffbfb}
 .card.unsure{border-left-color:#d9a200;background:#fffdf6}
 .vals{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;background:#f6f6f7;
   padding:6px 8px;border-radius:5px;line-height:1.7}
 .vals b{color:#555;font-weight:600}
 .why{color:#555;font-size:12.5px;margin:8px 0}
 .ask label{margin-right:14px} .note{width:100%;margin-top:6px;padding:4px 6px;font-size:13px}
 .find{float:right;font-size:12px;color:#0645ad;cursor:pointer;text-decoration:underline}
</style></head><body>
<header>
  <h1>Experiments to add</h1>
  <select id="pick"></select>
  <span class="count" id="paperCount"></span>
  <span class="grow"></span>
  <span class="count" id="total"></span>
  <button onclick="save()">Download answers</button>
</header>
<main><div id="text"></div><div id="cards"></div></main>
<script>
const DATA = __DATA__;
const answers = {};
const dois = Object.keys(DATA).sort();
const pick = document.getElementById('pick');
dois.forEach(d => pick.add(new Option(d + '  (' + DATA[d].records.length + ')', d)));

function total(){
  let n = 0, all = 0;
  dois.forEach(d => { DATA[d].records.forEach(r => { all++; if (answers[r.key]) n++; }); });
  document.getElementById('total').textContent = n + ' of ' + all + ' answered';
}

function attr(value){
  return value.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

function renderText(chunks){
  return chunks.map(c =>
    '<div class="chunk" id="k_' + c.id + '"><span class="cid">' + c.id + '</span>' + c.html + '</div>'
  ).join('');
}

function show(doi){
  const paper = DATA[doi];
  document.getElementById('text').innerHTML = renderText(paper.chunks);
  document.getElementById('paperCount').textContent = paper.records.length + ' to check';

  const box = document.getElementById('cards');
  box.innerHTML = '';
  const title = document.createElement('div');
  title.className = 'title';
  title.textContent = paper.title;
  box.appendChild(title);

  paper.records.forEach(r => {
    const saved = answers[r.key] || {};
    const card = document.createElement('div');
    card.className = 'card ' + (saved.answer || '');
    card.dataset.key = r.key;

    const link = document.createElement('span');
    link.className = 'find';
    link.textContent = 'show source';
    link.dataset.chunks = r.chunks.join(' ');
    link.dataset.term = String(r.values.catalyst || '');
    card.appendChild(link);

    const vals = document.createElement('div');
    vals.className = 'vals';
    vals.innerHTML = Object.entries(r.values)
      .map(([k, v]) => '<b>' + k + '</b> ' + String(v).replace(/[&<>]/g,
        c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))).join(' &middot; ');
    card.appendChild(vals);

    const why = document.createElement('div');
    why.className = 'why';
    why.textContent = r.reason;
    card.appendChild(why);

    const ask = document.createElement('div');
    ask.className = 'ask';
    [['yes','add it'], ['no','leave out'], ['unsure','not sure']].forEach(([value, label]) => {
      const box = document.createElement('label');
      const radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = r.key;
      radio.value = value;
      radio.checked = saved.answer === value;
      radio.addEventListener('change', () => {
        answers[r.key] = Object.assign(answers[r.key] || {}, {answer: value});
        card.className = 'card ' + value;
        total();
      });
      box.appendChild(radio);
      box.appendChild(document.createTextNode(' ' + label));
      ask.appendChild(box);
    });
    card.appendChild(ask);

    const note = document.createElement('input');
    note.className = 'note';
    note.placeholder = 'note';
    note.value = saved.note || '';
    note.addEventListener('input', () => {
      answers[r.key] = Object.assign(answers[r.key] || {}, {note: note.value});
    });
    card.appendChild(note);

    box.appendChild(card);
  });
  total();
}

document.getElementById('cards').addEventListener('click', event => {
  const link = event.target.closest('.find');
  if (!link) return;
  document.querySelectorAll('.chunk.hit').forEach(c => c.classList.remove('hit'));
  const ids = link.dataset.chunks ? link.dataset.chunks.split(' ') : [];
  let first = null;
  ids.forEach(id => {
    const el = document.getElementById('k_' + id);
    if (el){ el.classList.add('hit'); if (!first) first = el; }
  });
  if (first) first.scrollIntoView({block: 'start', behavior: 'smooth'});
  else alert('the cited text is not in this paper');
});

function save(){
  const out = [];
  dois.forEach(d => DATA[d].records.forEach(r => out.push({
    key: r.key, answer: (answers[r.key] || {}).answer || null,
    note: (answers[r.key] || {}).note || ''})));
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 2)], {type:'application/json'}));
  a.download = 'additions_confirmed.json'; a.click();
}

pick.onchange = () => show(pick.value);
show(dois[0]);
</script></body></html>"""

out = ARTIFACTS / "verify_additions.html"
out.write_text(page.replace("__DATA__", json.dumps(payload)))
print(f"wrote {out}  ({len(candidates)} experiments across {len(payload)} papers, "
      f"{out.stat().st_size // 1024} KB)")
