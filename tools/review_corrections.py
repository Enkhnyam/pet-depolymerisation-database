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

Built for speed, because there are 1,544 corrected records and the point is to get through a
sample of them: one correction per screen, digit keys to answer, and the next card is already
rendered. Nothing is uploaded; answers live in the browser until exported, the same arrangement
the adjudication pages use.

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
from review_database import FIELDS, LABELS, load_chunks, load_run, paper_title

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


def snippets(chunks: dict, cites: list, values: list, judge_cites: list) -> list[dict]:
    """The cited chunks, with the values under review marked inside them.

    This is the whole point of the source pane: a number is checked against the sentence it came
    from without opening the paper. Marking happens here rather than in the browser because a
    value's printed form differs from its stored one -- 0.5 against "0.50" -- and Python is
    holding both already.
    """
    ordered = [(c, "the record cites this") for c in cites if c in chunks]
    seen = {c for c, _ in ordered}
    ordered += [(c, "the judge cites this") for c in judge_cites
                if c in chunks and c not in seen]

    out = []
    for cite, why in ordered:
        text = chunks[cite][:2400]
        marks = set()
        for value in values:
            if value in (None, ""):
                continue
            marks.add(str(value))
            if isinstance(value, (int, float)):
                marks.add(f"{value:g}")
        out.append({"id": cite[:8], "why": why, "text": text,
                    "marks": sorted((m for m in marks if len(m) >= 2), key=len, reverse=True)})
    return out


def payload(sample: list[dict], corpus: Path) -> list[dict]:
    """Everything a card needs, as plain data. The browser renders, it does not compute."""
    titles, cache, cards = {}, {}, []
    for item in sample:
        doi = item["doi"]
        if doi not in cache:
            cache[doi] = load_chunks(corpus, doi)
            titles[doi] = paper_title(cache[doi])
        cards.append({
            **{key: item[key] for key in ("doi", "index", "field", "was", "to", "evidence",
                                          "critique", "drop", "fingerprint")},
            "title": titles[doi],
            "label": LABELS.get(item["field"], item["field"]),
            "record": item["record"],
            "chunks": snippets(cache[doi], item["cites"], [item["was"], item["to"]],
                               cited_ids(item["evidence"]) + cited_ids(item["critique"])),
        })
    return cards


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--ink:#12201F;--dim:#5D716E;--faint:#93A5A2;--rule:#DFE7E5;--panel:#F7FAF9;
  --was:#9C3F36;--to:#25517E;--ok:#2F6B4F;--warn:#9C3F36}
*{box-sizing:border-box}
body{margin:0;font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  color:var(--ink);background:#fff}
header{position:sticky;top:0;z-index:5;background:rgba(255,255,255,.95);
  backdrop-filter:blur(6px);border-bottom:1px solid var(--rule);padding:10px 20px;
  display:flex;align-items:center;gap:16px;flex-wrap:wrap}
h1{font-size:15px;margin:0;font-weight:640}
.count{font:12px ui-monospace,Menlo,monospace;color:var(--dim)}
.bar{flex:1;min-width:120px;height:6px;border-radius:99px;background:var(--rule);overflow:hidden}
.bar i{display:block;height:100%;background:var(--ok);width:0}
button{font:inherit;cursor:pointer;border-radius:8px;border:1.5px solid var(--rule);
  background:#fff;color:var(--ink);padding:7px 13px}
button:hover:not(:disabled){border-color:var(--dim)}
button:disabled{opacity:.45;cursor:default}
button.primary{background:var(--ink);color:#fff;border-color:var(--ink)}
.wrap{max-width:1080px;margin:0 auto;padding:22px 20px 90px}
.meta{font-size:12px;color:var(--dim);margin:0 0 4px}
.title{font-size:15px;font-weight:620;margin:0 0 14px}
.title a{color:var(--dim);font-size:12px;font-weight:400;margin-left:8px}
.diff{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 0 16px}
.side{border:1.5px solid var(--rule);border-radius:10px;padding:12px 14px}
.side.was{border-color:var(--was)}
.side.to{border-color:var(--to)}
.side .k{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--dim)}
.side .v{font:17px ui-monospace,Menlo,monospace;margin-top:4px;word-break:break-word}
.side.was .v{color:var(--was)}
.side.to .v{color:var(--to)}
.field{display:inline-block;font:11.5px ui-monospace,Menlo,monospace;background:var(--panel);
  border:1px solid var(--rule);border-radius:99px;padding:2px 9px;color:var(--dim)}
.why{background:var(--panel);border:1px solid var(--rule);border-radius:10px;
  padding:12px 14px;font-size:13px;margin:0 0 16px}
.why b{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.06em;
  color:var(--dim);margin-bottom:5px;font-weight:640}
.chunk{border-left:3px solid var(--rule);padding:2px 0 2px 12px;margin:0 0 12px;
  font-size:12.5px;color:#26403D;white-space:pre-wrap;max-height:230px;overflow:auto}
.chunk .cid{font:10.5px ui-monospace,Menlo,monospace;color:var(--faint);display:block;
  margin-bottom:3px}
mark{background:#FDF3C4;padding:0 2px;border-radius:3px}
.rec{font:11.5px ui-monospace,Menlo,monospace;color:var(--dim);margin:0 0 16px;
  display:flex;flex-wrap:wrap;gap:10px}
.answers{position:fixed;bottom:0;left:0;right:0;background:rgba(255,255,255,.97);
  border-top:1px solid var(--rule);padding:12px 20px;display:flex;gap:10px;
  justify-content:center;flex-wrap:wrap}
.answers button{min-width:210px;text-align:left}
.answers button kbd{font:11px ui-monospace,Menlo,monospace;background:var(--panel);
  border:1px solid var(--rule);border-radius:4px;padding:1px 5px;margin-right:8px}
.answers button.on{border-color:var(--ok);background:#EEF6F1}
.note{width:100%;max-width:640px;margin:8px auto 0;display:block;font:inherit;
  border:1.5px solid var(--rule);border-radius:8px;padding:7px 10px}
.done{text-align:center;padding:70px 20px;color:var(--dim)}
.done h2{color:var(--ink)}
.tag{font-size:11px;color:var(--warn);border:1px solid var(--warn);border-radius:99px;
  padding:1px 8px;margin-left:8px}
</style></head><body>
<header>
  <h1>__TITLE__</h1>
  <span class="count" id="count"></span>
  <span class="bar"><i id="bar"></i></span>
  <button id="prev">&larr; back</button>
  <button id="skip">skip</button>
  <button class="primary" id="export">Download decisions</button>
</header>
<div class="wrap" id="card"></div>
<div class="answers" id="answers"></div>
<script>
const DATA = __DATA__;
const ANSWERS = __ANSWERS__;
const KEY = 'pet-corrections-' + DATA.length;
const saved = JSON.parse(localStorage.getItem(KEY) || '{}');
const card = document.getElementById('card');
const answers = document.getElementById('answers');
const countEl = document.getElementById('count');
const barEl = document.getElementById('bar');
let cursor = 0;

function idOf(c) { return c.doi + '#' + c.index + '#' + c.field; }
function store() { localStorage.setItem(KEY, JSON.stringify(saved)); }
function esc(s) {
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function show(v) { return v === null || v === undefined || v === '' ? 'not reported' : String(v); }

function marked(chunk) {
  let html = esc(chunk.text);
  for (const m of chunk.marks) {
    // whitespace-tolerant around the decimal point: the markdown conversion splits numbers,
    // so the corpus holds "42. 7%" where the record holds 42.7, and an exact match highlights
    // nothing on exactly the cards where the number is the question
    const safe = esc(m).replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\\\./g, '\\s*\\.\\s*');
    html = html.replace(new RegExp('(?<![\\w>])' + safe + '(?![\\w])', 'g'), '<mark>$&</mark>');
  }
  return html;
}

function firstUnanswered() {
  const i = DATA.findIndex(c => !saved[idOf(c)]);
  return i < 0 ? DATA.length - 1 : i;
}

function render() {
  const c = DATA[cursor];
  const done = Object.keys(saved).length;
  countEl.textContent = (cursor + 1) + ' of ' + DATA.length + '  ·  ' + done + ' answered';
  barEl.style.width = (100 * done / DATA.length) + '%';
  document.getElementById('prev').disabled = cursor === 0;

  if (!c) { card.innerHTML = '<div class="done"><h2>Nothing to review</h2></div>'; return; }

  const rec = Object.entries(c.record)
    .filter(([, v]) => v !== null && v !== undefined && v !== '')
    .map(([k, v]) => '<span>' + esc(k) + ': ' + esc(v) + '</span>').join('');
  const chunks = c.chunks.length
    ? c.chunks.map(ch => '<div class="chunk"><span class="cid">chunk ' + esc(ch.id) + ' — ' +
        esc(ch.why) + '</span>' + marked(ch) + '</div>').join('')
    : '<div class="chunk"><em>the record cites no chunk that this paper contains</em></div>';

  card.innerHTML =
    '<p class="meta">' + esc(c.doi) + '  ·  record ' + c.index +
      '<span class="field" style="margin-left:8px">' + esc(c.field) + '</span>' +
      (c.drop ? '<span class="tag">judge also asked to drop this record</span>' : '') + '</p>' +
    '<p class="title">' + esc(c.title || '(title not found)') +
      '<a href="https://doi.org/' + encodeURIComponent(c.doi) + '" target="_blank" rel="noopener">open the paper</a></p>' +
    '<div class="diff">' +
      '<div class="side was"><div class="k">extractor wrote — ' + esc(c.label) + '</div>' +
        '<div class="v">' + esc(show(c.was)) + '</div></div>' +
      '<div class="side to"><div class="k">judge proposes — ' + esc(c.label) + '</div>' +
        '<div class="v">' + esc(show(c.to)) + '</div></div>' +
    '</div>' +
    '<div class="why"><b>evidence the judge cited</b>' + esc(c.evidence || '(none given)') + '</div>' +
    (c.critique ? '<div class="why"><b>the judge\'s reasoning for this record</b>' +
        esc(c.critique) + '</div>' : '') +
    '<div class="why"><b>the rest of the record as extracted</b><div class="rec">' + rec + '</div></div>' +
    '<div class="why"><b>source text the record cites</b>' + chunks + '</div>';

  const mine = saved[idOf(c)] || {};
  answers.innerHTML = ANSWERS.map(([value, text], i) =>
      '<button data-v="' + value + '"' + (mine.answer === value ? ' class="on"' : '') +
      '><kbd>' + (i + 1) + '</kbd>' + esc(text) + '</button>').join('') +
    '<input class="note" id="note" placeholder="optional note" value="' +
      esc(mine.note || '') + '">';

  answers.querySelectorAll('button').forEach(b =>
    b.onclick = () => answer(b.dataset.v));
  document.getElementById('note').oninput = e => {
    const id = idOf(c);
    saved[id] = Object.assign({}, saved[id], {note: e.target.value, field: c.field,
                                              fingerprint: c.fingerprint});
    store();
  };
}

function answer(value) {
  const c = DATA[cursor];
  saved[idOf(c)] = Object.assign({}, saved[idOf(c)], {
    answer: value, field: c.field, doi: c.doi, index: c.index,
    fingerprint: c.fingerprint, was: c.was, to: c.to,
    decided: new Date().toISOString()
  });
  store();
  cursor = Math.min(cursor + 1, DATA.length - 1);
  render();
  window.scrollTo(0, 0);
}

document.getElementById('prev').onclick = () => { cursor = Math.max(0, cursor - 1); render(); window.scrollTo(0, 0); };
document.getElementById('skip').onclick = () => { cursor = Math.min(cursor + 1, DATA.length - 1); render(); window.scrollTo(0, 0); };
document.getElementById('export').onclick = () => {
  const blob = new Blob([JSON.stringify({
    generated: new Date().toISOString(), sample: '__STAMP__',
    answered: Object.keys(saved).length, total: DATA.length, decisions: saved
  }, null, 1)], {type: 'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'corrections-decisions.json';
  a.click();
};
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  const i = ['1', '2', '3'].indexOf(e.key);
  if (i >= 0) { answer(ANSWERS[i][0]); return; }
  if (e.key === 'ArrowRight') document.getElementById('skip').click();
  if (e.key === 'ArrowLeft') document.getElementById('prev').click();
});

cursor = firstUnanswered();
render();
</script></body></html>
"""


def build(sample: list[dict], corpus: Path, title: str, stamp: str) -> str:
    page = (TEMPLATE
            .replace("__DATA__", json.dumps(payload(sample, corpus)))
            .replace("__ANSWERS__", json.dumps(ANSWERS))
            .replace("__TITLE__", title)
            .replace("__STAMP__", stamp))
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
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    out = Path(args.out) if args.out else OUT
    out.write_text(build(sample, ARTIFACTS / "data" / args.corpus, args.title, stamp),
                   encoding="utf-8")

    # The draw is written down. Re-running the sampler later draws a different sample and
    # silently re-weights records nobody saw; the manifest is what makes this one fixed history,
    # and the fingerprints let an ingest refuse a decision that has drifted onto another record.
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        "drawn": stamp, "seed": args.seed, "extraction": args.extraction,
        "judge": args.judge, "pool": len(pool), "size": len(sample),
        "by field": dict(Counter(c["field"] for c in sample)),
        "records": [{k: c[k] for k in ("doi", "index", "field", "was", "to", "fingerprint")}
                    for c in sample],
    }, indent=1), encoding="utf-8")

    print(f"\n{out.relative_to(ROOT)}  {out.stat().st_size / 1e6:.1f} MB, "
          f"{len(sample)} corrections")
    for field, n in Counter(c["field"] for c in sample).most_common():
        print(f"   {field:22s} {n:3d}")
    print(f"{MANIFEST.relative_to(ROOT)}  the draw, so it stays fixed")


if __name__ == "__main__":
    main()
