"""Sample the judge's proposed corrections and build a page for checking them one at a time.

The manuscript can say how often the judge's *flags* are right, because the chemists ruled on a
sample of flagged records. It cannot say how often the judge's *corrections* are right, and its
own Limitations section names that gap: "automatic corrections could introduce new mistakes".
Nothing in the pipeline measures whether they do. This is the tool for closing that.

It is a different question from the adjudication round and needs a different page. There, a
labeller forming a view must not see a grader's verdict. Here the judge's proposed value *is*
the thing under review, so it is shown alongside the extractor's, with the evidence the judge
cited and the source chunk that evidence came from. The reviewer answers one question -- which
value does the paper support -- and the answer is one of three, not free text.

Two panes, the arrangement the adjudication page already uses and the one that was asked for:
the paper on the left rendered as markdown so its tables survive -- reaction conditions live in
tables -- and that paper's corrections on the right. Selecting one marks the chunks behind it
and highlights, inside them, both the value the extractor wrote and the value the judge
proposes, so "which does the paper support" is answered from one screen. Digit keys answer;
answers live in the browser until exported, uploaded nowhere.

Both kinds of provenance are marked, because the record's own source_chunk_ids resolve to
nothing on some records: the chunks the record cites, and the chunks the judge quoted in its
evidence, which it writes with typographic hyphens rather than ASCII ones. On eleven of the
first hundred and twenty drawn, the judge's were the only source text there was.

Sampling is stratified by field and recorded. Corrections concentrate in the mass fields, so a
single pooled sample would say almost nothing about the ones that matter individually. And the
draw is written to a manifest beside the page, because an earlier round of this project learned
that re-running a sampler later draws a different sample and silently re-weights records nobody
saw: the manifest is what makes the sample fixed history, and it carries a fingerprint of each
record so an ingest can refuse a decision that has drifted onto a different experiment.

    review_corrections.py                          sample 120, stratified by field
    review_corrections.py --sample 40 --field catalyst_amount_g
    review_corrections.py --seed 7 --out /tmp/corrections.html
"""
import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from core.paths import ARTIFACTS
from core.schema import canonical_field

import _page
from build_adjudication import chunks_of
from review_database import FIELDS, LABELS, load_run, paper_title

RUNS = ARTIFACTS / "runs"
OUT = ARTIFACTS / "review_corrections.html"
MANIFEST = ARTIFACTS / "gold" / "corrections" / "sample.json"

# The judge cites chunk ids inside its own prose, and it writes them with typographic hyphens
# (U+2011 and friends) rather than ASCII ones. Eleven of the first 120 cards drawn had no source
# text at all from the record's own source_chunk_ids, and every one of them was recoverable from
# an id the judge had quoted -- so both are collected, and the dashes are normalised first.
UUID = re.compile(r"[0-9a-f]{8}[-\u2010-\u2015][0-9a-f]{4}[-\u2010-\u2015][0-9a-f]{4}"
                  r"[-\u2010-\u2015][0-9a-f]{4}[-\u2010-\u2015][0-9a-f]{12}", re.I)


def cited_ids(text: str) -> list[str]:
    return [re.sub(r"[\u2010-\u2015]", "-", m.group(0)).lower()
            for m in UUID.finditer(text or "")]


ANSWERS = [("judge", "the judge's value is right"),
           ("extractor", "the extractor's value is right"),
           ("neither", "neither, or the paper does not say")]


def sample_id(sample: list[dict]) -> str:
    """A name for this draw, derived from what was drawn.

    The page keys its saved answers on this. Keying on the generation time instead means
    regenerating the page silently orphans every answer already given -- which, for a page two
    supervisors are working through, is the worst bug it could have. The same draw reproduces
    the same id, so the work survives a rebuild.
    """
    rows = sorted(f"{c['doi']}#{c['index']}#{c['field']}" for c in sample)
    return hashlib.sha256("|".join(rows).encode()).hexdigest()[:12]


def fingerprint(record: dict) -> str:
    """Identity by content, not by position.

    A decision names a record by its index in a run, and an index is not an identity: a previous
    round attached a chemist's verdict to a different experiment exactly that way. Four fields
    that a re-extraction would have to preserve for the record to be the same experiment.
    """
    parts = [str(record.get(name, "")) for name in
             ("catalyst", "solvent", "temperature_c", "reaction_time_min")]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]


def corrections(extraction: Path, judge: Path) -> list[dict]:
    """Every field-level correction the judge proposed, with what it would replace."""
    extractions = load_run(extraction, "extractions")
    verdicts = load_run(judge, "verdicts")

    found = []
    for doi, payload in extractions.items():
        by_index = {v["extracted_index"]: v
                    for v in verdicts.get(doi, {}).get("verdicts", [])}
        for index, record in enumerate(payload["records"]):
            verdict = by_index.get(index)
            if not verdict:
                continue
            for fix in verdict.get("fixes") or []:
                # canonical_field because the judge names PET_amount_g both ways; cli/release.py
                # resolves it the same way, so the page and the released data agree on which
                # corrections exist
                field = canonical_field(fix.get("field"))
                if field is None or field not in FIELDS:
                    continue
                found.append({
                    "doi": doi, "index": index, "field": field,
                    "was": record.get(field), "to": fix.get("value"),
                    "evidence": fix.get("evidence", ""),
                    "critique": verdict.get("critique", ""),
                    "bad_fields": verdict.get("bad_fields") or [],
                    "drop": bool(verdict.get("drop_record")),
                    "cites": record.get("source_chunk_ids") or [],
                    "record": {name: record.get(name) for name in FIELDS},
                    "fingerprint": fingerprint(record),
                })
    return found


def draw(pool: list[dict], size: int, seed: int, only: str | None) -> list[dict]:
    """A sample spread over the fields, so each field's own precision is estimable.

    Proportional allocation would hand the smallest fields one or two records each and support no
    statement about them. This takes an equal share per field and gives back what a small field
    cannot fill, which is the same trade the adjudication strata make.
    """
    if only:
        pool = [c for c in pool if c["field"] == only]
    by_field = defaultdict(list)
    for item in pool:
        by_field[item["field"]].append(item)

    rng = random.Random(seed)
    for items in by_field.values():
        rng.shuffle(items)

    chosen, fields = [], sorted(by_field, key=lambda f: -len(by_field[f]))
    remaining = size
    while remaining > 0 and fields:
        share = max(1, remaining // len(fields))
        for field in list(fields):
            take = by_field[field][:share]
            chosen += take
            by_field[field] = by_field[field][len(take):]
            remaining -= len(take)
            if not by_field[field]:
                fields.remove(field)
            if remaining <= 0:
                break
    rng.shuffle(chosen)
    return chosen[:size]


def group(sample: list[dict], corpus: Path) -> list[dict]:
    """The sample as papers, each with its own corrections. The two-pane unit is a paper.

    Grouping is the point of the layout: a reviewer reads a paper once and then answers every
    correction drawn from it, instead of meeting the same paper on four separate screens.
    """
    papers: dict[str, dict] = {}
    for item in sample:
        entry = papers.setdefault(item["doi"], {"doi": item["doi"], "corrections": []})
        entry["corrections"].append({
            **{key: item[key] for key in ("index", "field", "was", "to", "evidence",
                                          "critique", "drop", "fingerprint")},
            "label": LABELS.get(item["field"], item["field"]),
            "record": item["record"],
            # Both sources of provenance. The record's own source_chunk_ids resolve to nothing
            # on some records, and the judge quotes chunk ids in its prose -- with typographic
            # hyphens -- which is the only source those cards have.
            "cites": item["cites"],
            "judge_cites": cited_ids(item["evidence"]) + cited_ids(item["critique"]),
        })

    for doi, entry in papers.items():
        entry["chunks"] = chunks_of(corpus, doi)
        entry["title"] = paper_title(
            {c["id"]: re.sub(r"<[^>]+>", " ", c["html"]) for c in entry["chunks"]})
        entry["corrections"].sort(key=lambda c: (c["index"], c["field"]))

    return sorted(papers.values(), key=lambda p: -len(p["corrections"]))


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#eef2f1;--panel:#fff;--ink:#16211f;--dim:#61756f;--line:#d8e2df;--soft:#f5f8f7;
 --ok:#3f6e46;--no:#a33a2e;--accent:#0e7c6b;--mark:#ffe08a;--markink:#4a3400;
 --cite:#fff8e6;--citeline:#e0b93c;--was:#a33a2e;--to:#25517e}
@media(prefers-color-scheme:dark){:root{--bg:#0b1312;--panel:#131e1d;--ink:#dde7e4;--dim:#8ea29e;
 --line:#243432;--soft:#0f1918;--ok:#7fb187;--no:#d98374;--accent:#4fc4ae;--mark:#6b5410;
 --markink:#ffeab5;--cite:#1d2417;--citeline:#7a6420;--was:#d98374;--to:#8aa8c6}}
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
button:disabled{opacity:.45;cursor:default}
.grow{flex:1}
.muted{color:var(--dim);font-size:.82rem}
.bar{width:120px;height:6px;border-radius:99px;background:var(--line);overflow:hidden}
.bar i{display:block;height:100%;background:var(--accent);width:0}
main{display:grid;grid-template-columns:1fr 1fr;min-height:0}
@media(max-width:1000px){main{grid-template-columns:1fr}}
#text,#recs{overflow-y:auto;padding:16px 20px;min-height:0}
#text{border-right:1px solid var(--line);background:var(--panel)}
.chunk{padding:2px 10px;border-left:3px solid transparent;border-radius:4px;margin-bottom:2px}
.chunk.cited{background:var(--cite);border-left-color:var(--citeline)}
.chunk.judgecite{border-left-style:dashed}
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
.rechead{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-bottom:9px}
.ix{font-family:ui-monospace,monospace;font-size:.76rem;color:var(--dim)}
.tag{font-size:.64rem;text-transform:uppercase;letter-spacing:.06em;padding:2px 7px;
 border-radius:4px;background:var(--soft);color:var(--dim)}
.tag.field{background:#e8eff3;color:#25517e}
.tag.drop{background:#f7e4e0;color:#8a2f22}
@media(prefers-color-scheme:dark){.tag.field{background:#17262e;color:#8aa8c6}
 .tag.drop{background:#2b1a17;color:#d98374}}
.diff{display:grid;grid-template-columns:1fr auto 1fr;gap:9px;align-items:center;
 margin-bottom:10px}
.pane{border:1px solid var(--line);border-radius:7px;padding:7px 10px;background:var(--soft)}
.pane k{display:block;font-size:.61rem;color:var(--dim);text-transform:uppercase;
 letter-spacing:.05em}
.pane v{font-size:1rem;font-variant-numeric:tabular-nums;word-break:break-word}
.pane.was{border-color:var(--was)} .pane.was v{color:var(--was)}
.pane.to{border-color:var(--to)} .pane.to v{color:var(--to)}
.arrow{color:var(--dim);font-size:1.1rem}
.ev{font-size:.82rem;color:var(--dim);border-top:1px solid var(--line);padding-top:8px;
 margin-bottom:9px}
.ev b{display:block;font-size:.61rem;text-transform:uppercase;letter-spacing:.05em;
 margin-bottom:3px;color:var(--dim);font-weight:640}
details{margin:0 0 9px}
summary{font-size:.78rem;color:var(--dim);cursor:pointer}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:5px;
 margin-top:7px}
.cell{background:var(--soft);border:1px solid var(--line);border-radius:5px;padding:4px 7px}
.cell k{display:block;font-size:.61rem;color:var(--dim);text-transform:uppercase;
 letter-spacing:.05em}
.cell v{font-size:.83rem;font-variant-numeric:tabular-nums}
.null{color:var(--dim);font-style:italic;font-size:.9em}
.ask{display:flex;gap:7px;align-items:center;flex-wrap:wrap;padding-top:9px;
 border-top:1px solid var(--line)}
.ask>span{font-size:.83rem;color:var(--dim);width:100%}
.vote kbd{font:11px ui-monospace,monospace;opacity:.65;margin-right:5px}
.vote.judge.on{background:var(--to);border-color:var(--to);color:#fff}
.vote.extractor.on{background:var(--was);border-color:var(--was);color:#fff}
.vote.neither.on{background:var(--dim);border-color:var(--dim);color:#fff}
.note{flex:1;min-width:130px;font-size:.8rem}
</style></head><body>
<div class="app">
<header>
  <h1>__TITLE__</h1>
  <select id="pick"></select>
  <span class="muted" id="stat"></span>
  <span class="grow"></span>
  <button id="back">&larr;</button>
  <button id="fwd">&rarr;</button>
  <span class="bar"><i id="bar"></i></span>
  <span class="muted" id="progress"></span>
  <button class="primary" id="export">Download decisions</button>
</header>
<main><div id="text"></div><div id="recs"></div></main>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const PAPERS = JSON.parse(document.getElementById('data').textContent);
const LABELS = __LABELS__;
const ANSWERS = __ANSWERS__;
const STAMP = '__STAMP__';
const TOTAL = PAPERS.reduce((n, p) => n + p.corrections.length, 0);
const KEY = 'pet-corrections-' + STAMP;
const saved = JSON.parse(localStorage.getItem(KEY) || '{}');
const RX_SPECIAL = /[.*+?^${}()|[\]\\]/g;
let current = 0;

const esc = s => String(s).replace(/[&<>"]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]);
const fmt = v => v === null || v === undefined || v === ''
  ? '<span class="null">not reported</span>' : esc(v);
const idOf = (doi, c) => doi + '#' + c.index + '#' + c.field;
function store() { localStorage.setItem(KEY, JSON.stringify(saved)); }

function forms(v) {
  if (v === null || v === undefined || v === '') return [];
  if (typeof v === 'string') return v.length > 2 ? [v] : [];
  const out = new Set([String(v)]);
  if (!Number.isInteger(v)) out.add(v.toFixed(1).replace(/\.0$/, ''));
  return [...out].filter(s => s.length > 1);
}

// Highlight inside text nodes only, so a value never lands inside a tag or a table border.
// The decimal point is allowed whitespace around it: the markdown conversion splits numbers,
// so the corpus holds "42. 7%" where the record holds 42.7, and an exact match would fail on
// exactly the cards where the number is the question.
function highlight(root, values) {
  const wanted = [];
  for (const v of values) for (const s of forms(v)) wanted.push(s);
  wanted.sort((a, b) => b.length - a.length);
  if (!wanted.length) return;
  const source = '(^|[^\\w.])(' + wanted.map(s =>
    s.replace(RX_SPECIAL, '\\$&').replace(/\\\./g, '\\s*\\.\\s*')).join('|') + ')(?![\\w.])';

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    if (!new RegExp(source).test(node.nodeValue)) continue;
    const span = document.createElement('span');
    span.innerHTML = esc(node.nodeValue).replace(new RegExp(source, 'g'), '$1<mark>$2</mark>');
    node.parentNode.replaceChild(span, node);
  }
}

function paperText(p) {
  return p.chunks.map(c => '<div class="chunk" data-id="' + c.id + '">' + c.html + '</div>')
    .join('') || '<p class="null">no text for this paper</p>';
}

function answered() { return Object.values(saved).filter(d => d && d.answer).length; }

function progress() {
  document.getElementById('progress').textContent = answered() + ' of ' + TOTAL + ' answered';
  document.getElementById('bar').style.width = (100 * answered() / TOTAL) + '%';
  document.getElementById('back').disabled = current === 0;
  document.getElementById('fwd').disabled = current === PAPERS.length - 1;
}

function fillPicker() {
  document.getElementById('pick').innerHTML = PAPERS.map((p, i) => {
    const done = p.corrections.filter(c => (saved[idOf(p.doi, c)] || {}).answer).length;
    return '<option value="' + i + '">' + (done === p.corrections.length ? '✓ ' : '') +
      esc((p.title || p.doi).slice(0, 70)) + '  (' + done + '/' + p.corrections.length + ')' +
      '</option>';
  }).join('');
  document.getElementById('pick').value = String(current);
}

function card(p, c) {
  const mine = saved[idOf(p.doi, c)] || {};
  const cells = Object.keys(c.record).map(f =>
    '<div class="cell"><k>' + esc(LABELS[f] || f) + '</k><v>' + fmt(c.record[f]) +
    '</v></div>').join('');
  const votes = ANSWERS.map(([value, text], i) =>
    '<button class="vote ' + value + (mine.answer === value ? ' on' : '') + '" data-v="' +
    value + '"><kbd>' + (i + 1) + '</kbd>' + esc(text) + '</button>').join('');
  return '<div class="rec' + (mine.answer ? ' done' : '') + '" data-i="' + c.index +
    '" data-f="' + esc(c.field) + '">' +
    '<div class="rechead"><span class="ix">#' + c.index + '</span>' +
      '<span class="tag field">' + esc(c.field) + '</span>' +
      (c.drop ? '<span class="tag drop">judge would drop this record</span>' : '') + '</div>' +
    '<div class="diff">' +
      '<div class="pane was"><k>extractor wrote</k><v>' + fmt(c.was) + '</v></div>' +
      '<div class="arrow">&rarr;</div>' +
      '<div class="pane to"><k>judge proposes</k><v>' + fmt(c.to) + '</v></div>' +
    '</div>' +
    '<div class="ev"><b>evidence the judge cited</b>' + esc(c.evidence || '(none given)') +
      '</div>' +
    (c.critique ? '<details><summary>the judge\'s full reasoning for this record</summary>' +
      '<div class="ev" style="border:0;padding-top:6px">' + esc(c.critique) + '</div></details>'
      : '') +
    '<details><summary>the record as extracted</summary><div class="grid">' + cells +
      '</div></details>' +
    '<div class="ask"><span>Which value does the paper support?</span>' + votes +
      '<input class="note" placeholder="note (optional)" value="' + esc(mine.note || '') +
      '"></div></div>';
}

function drawPaper() {
  const p = PAPERS[current];
  document.getElementById('stat').textContent = p.corrections.length + ' correction' +
    (p.corrections.length === 1 ? '' : 's') + ' · ' + p.doi;
  document.getElementById('text').innerHTML = paperText(p);
  document.getElementById('recs').innerHTML = p.corrections.map(c => card(p, c)).join('');

  document.querySelectorAll('#recs .rec').forEach(el => {
    const c = p.corrections.find(x => x.index === Number(el.dataset.i) &&
                                      x.field === el.dataset.f);
    el.addEventListener('click', event => {
      if (event.target.tagName === 'BUTTON' || event.target.tagName === 'INPUT') return;
      select(c, el);
    });
    el.querySelectorAll('.vote').forEach(b =>
      b.onclick = () => decide(p, c, b.dataset.v, el));
    el.querySelector('.note').onchange = e => {
      const id = idOf(p.doi, c);
      saved[id] = Object.assign({}, saved[id], {note: e.target.value || null});
      store();
    };
  });

  if (p.corrections.length) select(p.corrections[0], document.querySelector('#recs .rec'));
  fillPicker();
  progress();
}

// Both provenance sources are marked, and differently: the chunks the record cites, and the
// chunks the judge quoted in its evidence. Some records cite nothing that resolves, and then
// the judge's are the only source text there is.
function select(c, element) {
  document.querySelectorAll('#recs .rec').forEach(el => el.classList.remove('on'));
  if (element) element.classList.add('on');

  const p = PAPERS[current];
  document.getElementById('text').innerHTML = paperText(p);
  const own = new Set(c.cites);
  const theirs = new Set(c.judge_cites.filter(id => !own.has(id)));
  let first = null;
  document.querySelectorAll('#text .chunk').forEach(el => {
    const id = el.dataset.id;
    if (!own.has(id) && !theirs.has(id)) return;
    el.classList.add('cited');
    if (theirs.has(id)) el.classList.add('judgecite');
    highlight(el, [c.was, c.to]);
    if (!first) first = el;
  });
  if (first) first.scrollIntoView({behavior: 'smooth', block: 'center'});
}

function decide(p, c, value, element) {
  const id = idOf(p.doi, c);
  saved[id] = Object.assign({}, saved[id], {
    doi: p.doi, extracted_index: c.index, field: c.field, answer: value,
    was: c.was, to: c.to, fingerprint: c.fingerprint,
    decided: new Date().toISOString()
  });
  store();
  element.classList.add('done');
  element.querySelectorAll('.vote').forEach(b =>
    b.classList.toggle('on', b.dataset.v === value));
  fillPicker();
  progress();

  const next = element.nextElementSibling;
  if (next && next.classList.contains('rec')) {
    const c2 = p.corrections.find(x => x.index === Number(next.dataset.i) &&
                                       x.field === next.dataset.f);
    select(c2, next);
    next.scrollIntoView({behavior: 'smooth', block: 'nearest'});
  }
}

function go(i) {
  current = Math.min(PAPERS.length - 1, Math.max(0, i));
  drawPaper();
  document.getElementById('recs').scrollTo(0, 0);
}

document.getElementById('pick').onchange = e => go(Number(e.target.value));
document.getElementById('back').onclick = () => go(current - 1);
document.getElementById('fwd').onclick = () => go(current + 1);
document.getElementById('export').onclick = () => {
  const blob = new Blob([JSON.stringify({
    generated: new Date().toISOString(), sample: STAMP,
    answered: answered(), total: TOTAL, decisions: saved
  }, null, 1)], {type: 'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'corrections-decisions.json';
  a.click();
};
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  const on = document.querySelector('#recs .rec.on');
  const i = ['1', '2', '3'].indexOf(e.key);
  if (i >= 0 && on) { on.querySelectorAll('.vote')[i].click(); return; }
  if (e.key === 'ArrowRight') go(current + 1);
  if (e.key === 'ArrowLeft') go(current - 1);
});

drawPaper();
</script></body></html>
"""


def build(sample: list[dict], corpus: Path, title: str, drawn: str) -> str:
    # "</" is escaped because the payload rides in a <script type="application/json"> block and
    # the judge's prose can contain anything; a literal </script> inside it would end the tag.
    page = (TEMPLATE
            .replace("__DATA__", json.dumps(group(sample, corpus), ensure_ascii=False)
                     .replace("</", "<\\/"))
            .replace("__LABELS__", json.dumps(LABELS))
            .replace("__ANSWERS__", json.dumps(ANSWERS))
            .replace("__TITLE__", title)
            .replace("__STAMP__", drawn))
    _page.validate(page)
    return page


def main() -> None:
    parser = argparse.ArgumentParser(prog="review_corrections")
    parser.add_argument("--extraction", default="mass_luna_1shot")
    parser.add_argument("--judge", default="mass_oss_1shot/mass_oss_1shot")
    parser.add_argument("--corpus", default="corpus_markdown")
    parser.add_argument("--sample", type=int, default=120,
                        help="how many corrections to draw (0 for all)")
    parser.add_argument("--field", default=None, help="restrict to one field")
    parser.add_argument("--seed", type=int, default=20260909)
    parser.add_argument("--out", default=None)
    parser.add_argument("--title", default="Verify the judge's corrections")
    args = parser.parse_args()

    pool = corrections(RUNS / args.extraction, RUNS / args.judge)
    print(f"{len(pool):,} field-level corrections across "
          f"{len({(c['doi'], c['index']) for c in pool}):,} records")
    for field, n in Counter(c["field"] for c in pool).most_common():
        print(f"   {field:22s} {n:5,}")

    sample = pool if not args.sample else draw(pool, args.sample, args.seed, args.field)
    drawn = sample_id(sample)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    out = Path(args.out) if args.out else OUT
    out.write_text(build(sample, ARTIFACTS / "data" / args.corpus, args.title, drawn),
                   encoding="utf-8")

    # The draw is written down. Re-running the sampler later draws a different sample and
    # silently re-weights records nobody saw; the manifest is what makes this one fixed history,
    # and the fingerprints let an ingest refuse a decision that has drifted onto another record.
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        "sample": drawn, "drawn": stamp, "seed": args.seed, "extraction": args.extraction,
        "judge": args.judge, "pool": len(pool), "size": len(sample),
        "by field": dict(Counter(c["field"] for c in sample)),
        "records": [{k: c[k] for k in ("doi", "index", "field", "was", "to", "fingerprint")}
                    for c in sample],
    }, indent=1), encoding="utf-8")

    print(f"\n{out.relative_to(ROOT)}  {out.stat().st_size / 1e6:.1f} MB, "
          f"{len(sample)} corrections across "
          f"{len({c['doi'] for c in sample})} papers, sample {drawn}")
    for field, n in Counter(c["field"] for c in sample).most_common():
        print(f"   {field:22s} {n:3d}")
    print(f"{MANIFEST.relative_to(ROOT)}  the draw, so it stays fixed")


if __name__ == "__main__":
    main()
