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

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from core.paths import ARTIFACTS
from core.schema import canonical_field

import _page
from build_adjudication import chunks_of
from build_release import MULTI_CATALYST
from core.solubility import classify
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


# The release's own inclusion rules, applied to the sample before anything is drawn.
#
# This page used to draw from the raw extraction run, which is every record the extractor
# produced across all 1,026 papers -- including everything the release exists to remove. Of the
# first 120 cards, 18 were heterogeneous catalysis, 15 were catalysts that resolve to no
# compound at all and 17 were uncatalysed baselines: 50 of 120 were records the database would
# never ship, and an hour spent ruling on them says nothing about the data that is published.
# The filtering had not failed; it had never been reached. It lives in build_release.py, one
# stage downstream of the run this page reads.
#
# So the rules are imported rather than restated. core.solubility.classify and build_release's
# MULTI_CATALYST are the same objects the release calls, so a card shown here is a record the
# release carries by construction -- not by two spellings of the rule that happen to agree
# today. FIELDS is the same list the metric scores.
FULL = ARTIFACTS / "huggingface" / "full" / "records-00000-of-00001.parquet"

# Dropped on top of the release's rules. Acid and base catalysis is a different chemistry from
# the solvated-metal and ionic-liquid systems this corpus was assembled for, and it is the class
# where a "correction" most often turns on a reporting convention rather than on what the paper
# says -- the two things this round is trying to tell apart.
EXCLUDED_CLASSES = {"acid or base"}

# Fields a record must carry before it is worth a reviewer's screen. A card whose record holds
# three of eleven fields gives no context to judge the fourth against, and the sample was full
# of them. Eight leaves 446 corrections over 310 records and all 11 fields still represented,
# which is enough to draw 120 stratified; nine collapses to 20 papers and loses conversion.
MIN_FIELDS = 8


def eligible(minimum: int, rules: bool = True) -> dict[tuple[str, int], int]:
    """The records worth a reviewer's screen, each with the number of fields it carries.

    Returns {(doi, index): fields filled}. Membership is the filter; the value is what the
    draw's preference for full records reads. `rules` off keeps the completeness floor and
    drops the chemistry -- the escape hatch for looking at the raw run deliberately.
    """
    frame = pd.read_parquet(FULL)
    frame["phase"] = [classify(str(n), str(s or ""), str(t or ""))[0] for n, s, t in
                      zip(frame.catalyst, frame.catalyst_smiles, frame.catalyst_smiles_tier)]
    frame["single"] = ~frame.catalyst.astype(str).str.contains(MULTI_CATALYST, na=False)
    frame["filled"] = frame[[f for f in FIELDS if f in frame.columns]].notna().sum(axis=1)

    keep = frame[frame.filled.ge(minimum)]
    if rules:
        keep = keep[keep.phase.eq("homogeneous") & keep.single
                    & ~keep.catalyst_class.isin(EXCLUDED_CLASSES)]
    return {(doi, int(index)): int(filled) for doi, index, filled
            in zip(keep.doi, keep.record_index, keep.filled)}


# What a reviewer can say about a card. The first three are the original question -- which value
# does the paper support -- and the fourth is the one the first round of reviewing kept needing
# and could not express: the extractor wrote something defensible because the prompt never
# covered the case, AND the judge was right to notice it. Neither did badly, and forcing that
# onto "judge" or "extractor" throws away the only interesting thing about the card.
#
# They are not exclusive. A correction can be a case where the judge is right about the value
# and both parties are reasonable about the edge case, and a reviewer who has to pick one says
# less than one who can pick both.
ANSWERS = [("judge", "the judge's value is right"),
           ("extractor", "the extractor's value is right"),
           ("both", "both defensible -- e.g. prompt gap, judge right to flag"),
           ("neither", "neither, or the paper does not say")]

# Asked separately from the answer, because "who is right" and "how much it matters" are
# different questions and collapsing them loses both. A record can be wrong in a way no
# downstream user would notice, and right in a way that would have poisoned a fit.
SEVERITY = [("severe_extraction", "the extractor's error is severe"),
            ("severe_judge", "the judge's error is severe")]


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


def draw(pool: list[dict], size: int, seed: int, only: str | None,
         fullness: dict[tuple[str, int], int]) -> list[dict]:
    """A sample spread over the fields, so each field's own precision is estimable.

    Proportional allocation would hand the smallest fields one or two records each and support no
    statement about them. This takes an equal share per field and gives back what a small field
    cannot fill, which is the same trade the adjudication strata make.

    Two things decide which records are available to it. `fullness` is the eligibility map, so a
    record the release would not ship is not drawable at all; and within each field the fullest
    records go first, because a correction to one field is only judgeable against the rest of the
    record and a card carrying three values of eleven gives a reviewer nothing to judge against.
    The shuffle happens before the sort and the sort is stable, so records tied on completeness
    are still drawn at random -- the preference orders the strata, it does not pick the records.
    """
    if only:
        pool = [c for c in pool if c["field"] == only]
    pool = [c for c in pool if (c["doi"], c["index"]) in fullness]
    by_field = defaultdict(list)
    for item in pool:
        by_field[item["field"]].append(item)

    rng = random.Random(seed)
    for items in by_field.values():
        rng.shuffle(items)
        items.sort(key=lambda c: -fullness[(c["doi"], c["index"])])

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
                                          "critique", "drop", "filled", "fingerprint")},
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
 --cite:#fff2cf;--citeline:#8a6410;--was:#a33a2e;--to:#25517e;--ctx:#bfe0d6;--ctxink:#123f34}
@media(prefers-color-scheme:dark){:root{--bg:#0b1312;--panel:#131e1d;--ink:#dde7e4;--dim:#8ea29e;
 --line:#243432;--soft:#0f1918;--ok:#7fb187;--no:#d98374;--accent:#4fc4ae;--mark:#6b5410;
 --markink:#ffeab5;--cite:#2c2614;--citeline:#c39c33;--was:#d98374;--to:#8aa8c6;
 --ctx:#1f4238;--ctxink:#a8dbc9}}
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
/* The block signal and the value marks have to read at the same time, and they used not to
   compete: marking only ever happened inside cited chunks, so "the chunk with the colour in it"
   was the cited chunk and a 7/255 cream tint was enough to confirm it. Now that every chunk is
   marked, that tint says nothing -- the block has to carry its own weight. A stronger ground, a
   4px rule, a ring, and a label naming which kind of citation it is.

   The label is ::before rather than an element, deliberately: highlight() walks text nodes, and
   a label in the DOM would be text the marker could match inside. Generated content is invisible
   to a TreeWalker, so the two systems cannot collide. */
.chunk.cited{background:var(--cite);border-left-color:var(--citeline);border-left-width:4px;
 box-shadow:0 0 0 1px var(--citeline);padding:6px 10px 4px;margin:6px 0}
.chunk.cited::before{content:"cited by the record";display:block;font-size:.58rem;
 font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--citeline);
 margin-bottom:4px}
.chunk.judgecite{border-left-style:dashed}
.chunk.judgecite::before{content:"cited by the judge"}
.chunk h3,.chunk h4,.chunk h5,.chunk h6{font-size:.92rem;margin:14px 0 6px}
.chunk p{margin:0 0 8px}
.chunk ul{margin:0 0 8px;padding-left:20px}
.chunk table{border-collapse:collapse;width:100%;margin:8px 0;font-size:.82rem;display:block;
 overflow-x:auto}
.chunk th,.chunk td{border:1px solid var(--line);padding:4px 7px;text-align:left;
 white-space:nowrap}
.chunk th{background:var(--soft);font-weight:600}
mark{background:var(--mark);color:var(--markink);border-radius:2px;padding:0 2px;font-weight:600}
/* The rest of the record, marked in the second colour. The correction under review is one
   number, and one number on its own is findable in a dozen places in a paper; the row it came
   from is not. Marking the record's other values makes the source row light up as a group, so
   a reviewer confirms they are reading the right experiment before ruling on the field. */
mark.ctx{background:var(--ctx);color:var(--ctxink);font-weight:500}
.key{display:flex;gap:14px;flex-wrap:wrap;font-size:.72rem;color:var(--dim);
 padding:0 0 10px;border-bottom:1px solid var(--line);margin-bottom:12px}
.key i{font-style:normal;border-radius:2px;padding:0 5px}
.key i.a{background:var(--mark);color:var(--markink);font-weight:600}
.key i.b{background:var(--ctx);color:var(--ctxink)}
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
.found{font-size:.75rem;color:var(--was);min-height:0;padding:2px 0}
.ask{display:flex;gap:7px;align-items:center;flex-wrap:wrap;padding-top:9px;
 border-top:1px solid var(--line)}
.ask>span{font-size:.83rem;color:var(--dim);width:100%}
.vote kbd{font:11px ui-monospace,monospace;opacity:.65;margin-right:5px}
.vote.judge.on{background:var(--to);border-color:var(--to);color:#fff}
.vote.extractor.on{background:var(--was);border-color:var(--was);color:#fff}
.vote.neither.on{background:var(--dim);border-color:var(--dim);color:#fff}
.vote.both.on{background:var(--ok);border-color:var(--ok);color:#fff}
/* Severity is a separate row, not another vote. Merging them would make "the judge is right"
   and "this one mattered" compete for the same click. */
.sev{display:flex;gap:14px;flex-wrap:wrap;width:100%;padding-top:8px;
 border-top:1px dashed var(--line);margin-top:4px}
.sev label{display:flex;gap:5px;align-items:center;font-size:.78rem;color:var(--dim);
 cursor:pointer}
.sev input{width:14px;height:14px;padding:0;accent-color:var(--no)}
.tag.fill{background:var(--soft);color:var(--dim);font-variant-numeric:tabular-nums}
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
const SEVERITY = __SEVERITY__;
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
//
// Two groups in one pass, not two passes. A second pass would walk text already wrapped by the
// first and nest one mark inside another; and the groups overlap by design -- a value can be
// both the correction under review and one of the record's other fields -- so the last group
// naming a string wins it. Callers pass the context first and the correction last.
const tidy = s => s.replace(/\s*\.\s*/g, '.');

function highlight(root, groups) {
  const cls = new Map();
  for (const g of groups)
    for (const v of g.values) for (const s of forms(v)) cls.set(s, g.cls);
  if (!cls.size) return;
  const wanted = [...cls.keys()].sort((a, b) => b.length - a.length);
  const source = '(^|[^\\w.])(' + wanted.map(s =>
    s.replace(RX_SPECIAL, '\\$&').replace(/\\\./g, '\\s*\\.\\s*')).join('|') + ')(?![\\w.])';

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    if (!new RegExp(source).test(node.nodeValue)) continue;
    const span = document.createElement('span');
    span.innerHTML = esc(node.nodeValue).replace(new RegExp(source, 'g'), (m, pre, hit) => {
      // the matched text can carry the split decimal the pattern allows, so the class is
      // looked up on the tidied form as well as on the literal one
      const c = cls.get(hit) ?? cls.get(tidy(hit)) ?? '';
      return pre + '<mark' + (c ? ' class="' + c + '"' : '') + '>' + hit + '</mark>';
    });
    node.parentNode.replaceChild(span, node);
  }
}

// Every value the record carries except the field being corrected -- the conditions and the
// outcomes both, because what a reviewer is really doing on the left is finding the one table
// row this experiment came from, and the row is identified by the values that are NOT in
// question. The corrected field is left out: the extractor's value for it is already shown as
// the primary mark, and marking it twice in two colours says nothing.
function context(c) {
  return Object.entries(c.record)
    .filter(([f, v]) => f !== c.field && v !== null && v !== undefined && v !== '')
    .map(([, v]) => v);
}

function paperText(p) {
  const key = '<div class="key"><span><i class="a">value under review</i></span>' +
    '<span><i class="b">the rest of this record</i></span>' +
    '<span>shaded blocks are the chunks cited; dashed edge = cited by the judge only</span>' +
    '</div>';
  return key + (p.chunks.map(c => '<div class="chunk" data-id="' + c.id + '">' + c.html +
    '</div>').join('') || '<p class="null">no text for this paper</p>');
}

function answered() {
  return Object.values(saved).filter(d => d && (d.answers || []).length).length;
}

function progress() {
  document.getElementById('progress').textContent = answered() + ' of ' + TOTAL + ' answered';
  document.getElementById('bar').style.width = (100 * answered() / TOTAL) + '%';
  document.getElementById('back').disabled = current === 0;
  document.getElementById('fwd').disabled = current === PAPERS.length - 1;
}

function fillPicker() {
  document.getElementById('pick').innerHTML = PAPERS.map((p, i) => {
    const done = p.corrections.filter(c =>
      answersOf(saved[idOf(p.doi, c)] || {}).length).length;
    return '<option value="' + i + '">' + (done === p.corrections.length ? '✓ ' : '') +
      esc((p.title || p.doi).slice(0, 70)) + '  (' + done + '/' + p.corrections.length + ')' +
      '</option>';
  }).join('');
  document.getElementById('pick').value = String(current);
}

function answersOf(mine) { return mine.answers || []; }

function card(p, c) {
  const mine = saved[idOf(p.doi, c)] || {};
  const chosen = answersOf(mine);
  const cells = Object.keys(c.record).map(f =>
    '<div class="cell"><k>' + esc(LABELS[f] || f) + '</k><v>' + fmt(c.record[f]) +
    '</v></div>').join('');
  const votes = ANSWERS.map(([value, text], i) =>
    '<button class="vote ' + value + (chosen.includes(value) ? ' on' : '') + '" data-v="' +
    value + '"><kbd>' + (i + 1) + '</kbd>' + esc(text) + '</button>').join('');
  const sev = SEVERITY.map(([value, text]) =>
    '<label><input type="checkbox" data-s="' + value + '"' + (mine[value] ? ' checked' : '') +
    '>' + esc(text) + '</label>').join('');
  return '<div class="rec' + (chosen.length ? ' done' : '') + '" data-i="' + c.index +
    '" data-f="' + esc(c.field) + '">' +
    '<div class="rechead"><span class="ix">#' + c.index + '</span>' +
      '<span class="tag field">' + esc(c.field) + '</span>' +
      '<span class="tag fill">' + c.filled + '/' + Object.keys(c.record).length +
        ' fields</span>' +
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
    '<details open><summary>the record as extracted &mdash; its other values are marked '
      + 'on the left</summary><div class="grid">' + cells + '</div></details>' +
    '<div class="found"></div>' +
    '<div class="ask"><span>Which value does the paper support? Pick every one that '
      + 'applies.</span>' + votes +
      '<input class="note" placeholder="note (optional)" value="' + esc(mine.note || '') +
      '">' + '<div class="sev">' + sev + '</div></div></div>';
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
      if (['BUTTON', 'INPUT', 'LABEL'].includes(event.target.tagName)) return;
      select(c, el);
    });
    el.querySelectorAll('.vote').forEach(b =>
      b.onclick = () => toggle(p, c, b.dataset.v, el));
    el.querySelectorAll('.sev input').forEach(b =>
      b.onchange = e => severity(p, c, b.dataset.s, e.target.checked));
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

  // the record's other fields first, then the two values under review, so a value that is
  // both keeps the colour of the question rather than the colour of the context
  const groups = [{values: context(c), cls: 'ctx'}, {values: [c.was, c.to], cls: ''}];

  // Every chunk, not only the cited ones. Marking was inside the "is this chunk cited" guard,
  // and the cited chunks are a median 2% of a paper -- so the value a reviewer was looking for
  // was unmarked 98% of the time and the panel looked broken. Citation is a different claim
  // from presence: the shading still says which chunks the record and the judge pointed at,
  // and the marks now say where the numbers actually are. A value the extractor invented
  // shows up precisely as a value with no mark anywhere, which is the answer to the card.
  let cited = null, found = null;
  document.querySelectorAll('#text .chunk').forEach(el => {
    const id = el.dataset.id;
    if (own.has(id) || theirs.has(id)) {
      el.classList.add('cited');
      if (theirs.has(id)) el.classList.add('judgecite');
      if (!cited) cited = el;
    }
    highlight(el, groups);
    if (!found && el.querySelector('mark:not(.ctx)')) found = el;
  });

  // Scroll to the value under review if it is anywhere in the paper, and only fall back to the
  // first cited chunk when it is not: the cited chunk is where the judge says to look, the
  // mark is where the number actually is, and when they differ the number wins.
  const target = found || cited;
  if (target) target.scrollIntoView({behavior: 'smooth', block: 'center'});
  note(element, !!found);
}

// Says so when the value under review appears nowhere in the paper text. Without it, "no mark
// on the left" and "highlighting is broken" look identical -- and for a correction that removes
// an invented number, no mark is the finding.
function note(element, found) {
  if (!element) return;
  const slot = element.querySelector('.found');
  if (slot) slot.textContent = found ? '' : 'this value does not appear in the paper text';
}

// Answers toggle rather than replace, because more than one can be true at once: the judge's
// value can be right AND both parties defensible, and a reviewer forced to pick one says less
// than one who can say both.
//
// This is also why the card no longer advances by itself. Advancing on the first click was
// right when the first click was the whole answer; with a set to build it would carry the
// reviewer away mid-answer. Enter moves on, and the card stays put until then.
function toggle(p, c, value, element) {
  const id = idOf(p.doi, c);
  const mine = saved[id] || {};
  const chosen = new Set(answersOf(mine));
  chosen.has(value) ? chosen.delete(value) : chosen.add(value);
  saved[id] = Object.assign({}, mine, {
    doi: p.doi, extracted_index: c.index, field: c.field, answers: [...chosen],
    was: c.was, to: c.to, filled: c.filled, fingerprint: c.fingerprint,
    decided: new Date().toISOString()
  });
  store();
  element.classList.toggle('done', chosen.size > 0);
  element.querySelectorAll('.vote').forEach(b =>
    b.classList.toggle('on', chosen.has(b.dataset.v)));
  fillPicker();
  progress();
}

// Severity is recorded whether or not an answer has been given: "the judge's error is severe"
// is a fact about the card, not a qualifier on a vote.
function severity(p, c, value, on) {
  const id = idOf(p.doi, c);
  saved[id] = Object.assign({}, saved[id], {
    doi: p.doi, extracted_index: c.index, field: c.field,
    was: c.was, to: c.to, filled: c.filled, fingerprint: c.fingerprint,
    [value]: on || null, decided: new Date().toISOString()
  });
  store();
}

function step(p, element) {
  const next = element.nextElementSibling;
  if (!next || !next.classList.contains('rec')) return;
  const c2 = p.corrections.find(x => x.index === Number(next.dataset.i) &&
                                     x.field === next.dataset.f);
  select(c2, next);
  next.scrollIntoView({behavior: 'smooth', block: 'nearest'});
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
  const i = ANSWERS.map((_, n) => String(n + 1)).indexOf(e.key);
  if (i >= 0 && on) { on.querySelectorAll('.vote')[i].click(); return; }
  // severity without reaching for the mouse: e for the extractor's, j for the judge's
  const sev = {e: 'severe_extraction', j: 'severe_judge'}[e.key.toLowerCase()];
  if (sev && on) {
    const box = on.querySelector('.sev input[data-s="' + sev + '"]');
    if (box) { box.checked = !box.checked; box.dispatchEvent(new Event('change')); }
    return;
  }
  if (e.key === 'Enter' && on) { step(PAPERS[current], on); return; }
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
            .replace("__SEVERITY__", json.dumps(SEVERITY))
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
    parser.add_argument("--min-fields", type=int, default=MIN_FIELDS,
                        help="fields a record must carry to be drawable")
    parser.add_argument("--all-phases", action="store_true",
                        help="draw from the raw run, without the release's inclusion rules")
    parser.add_argument("--seed", type=int, default=20260909)
    parser.add_argument("--out", default=None)
    parser.add_argument("--title", default="Verify the judge's corrections")
    args = parser.parse_args()

    pool = corrections(RUNS / args.extraction, RUNS / args.judge)
    print(f"{len(pool):,} field-level corrections across "
          f"{len({(c['doi'], c['index']) for c in pool}):,} records in the raw run")

    # What the rules leave, reported as a funnel rather than as a final number: the question
    # this page's first round raised was "how did these land in our sample", and the answer is
    # only legible if each rule's cost is visible.
    fullness = eligible(args.min_fields, rules=not args.all_phases)
    for item in pool:
        item["filled"] = fullness.get((item["doi"], item["index"]), 0)

    drawable = [c for c in pool if (c["doi"], c["index"]) in fullness]
    print("   " + (f"--all-phases: chemistry rules OFF, {args.min_fields}+ fields only"
                   if args.all_phases else
                   f"homogeneous, single-component, "
                   f"not {'/'.join(sorted(EXCLUDED_CLASSES))}, {args.min_fields}+ fields"))
    print(f"   {len(drawable):,} drawable across "
          f"{len({(c['doi'], c['index']) for c in drawable}):,} records, "
          f"{len({c['doi'] for c in drawable})} papers")
    for field, n in Counter(c["field"] for c in drawable).most_common():
        print(f"      {field:22s} {n:5,}")

    sample = pool if not args.sample else draw(pool, args.sample, args.seed, args.field,
                                               fullness)
    drawn = sample_id(sample)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    out = Path(args.out) if args.out else OUT
    out.write_text(build(sample, ARTIFACTS / "data" / args.corpus, args.title, drawn),
                   encoding="utf-8")

    # The draw is written down. Re-running the sampler later draws a different sample and
    # silently re-weights records nobody saw; the manifest is what makes this one fixed history,
    # and the fingerprints let an ingest refuse a decision that has drifted onto another record.
    # The manifest follows the page. It used to be written to the one fixed path whatever
    # --out said, so a throwaway run against /tmp silently overwrote the record of the draw
    # two supervisors were working through -- the one file in this tool that must not move.
    manifest = (Path(args.out).with_suffix(".json") if args.out else MANIFEST)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({
        "sample": drawn, "drawn": stamp, "seed": args.seed, "extraction": args.extraction,
        "judge": args.judge, "pool": len(pool), "size": len(sample),
        # The eligibility rules travel with the draw. A manifest that records which records were
        # sampled but not which records could have been sampled cannot be re-derived later.
        "filter": {
            "phase": None if args.all_phases else "homogeneous",
            "single_component": None if args.all_phases else True,
            "excluded_classes": [] if args.all_phases else sorted(EXCLUDED_CLASSES),
            "min_fields": args.min_fields,
            "drawable": len(drawable),
        },
        "by field": dict(Counter(c["field"] for c in sample)),
        "records": [{k: c[k] for k in ("doi", "index", "field", "was", "to", "filled",
                                       "fingerprint")}
                    for c in sample],
    }, indent=1), encoding="utf-8")

    print(f"\n{out.relative_to(ROOT)}  {out.stat().st_size / 1e6:.1f} MB, "
          f"{len(sample)} corrections across "
          f"{len({c['doi'] for c in sample})} papers, sample {drawn}")
    for field, n in Counter(c["field"] for c in sample).most_common():
        print(f"   {field:22s} {n:3d}")
    print(f"{manifest}  the draw, so it stays fixed")


if __name__ == "__main__":
    main()
