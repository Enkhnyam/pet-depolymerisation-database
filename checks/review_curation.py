import glob
import hashlib
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
from markdown_it import MarkdownIt

sys.path.insert(0, str(Path(__file__).parent))
from _setup import ARTIFACTS, data_path, curated_table

renderer = MarkdownIt("commonmark").enable("table")

SOURCE_CSV = "pet_il_combined.csv"
FIELDS = ["catalyst", "solvent", "temperature_c", "reaction_time_min", "catalyst_amount_g",
          "PET_amount_g", "solvent_amount_g", "yield_percent", "selectivity_percent",
          "conversion_percent", "pressure_atm"]
KEY_NUMBERS = ["temperature_c", "reaction_time_min", "yield_percent"]
REVIEW_LABELS = {"10.1039/d5gc01998b": "review A", "10.1021/acs.iecr.3c04481": "review B"}


def doi_key(value):
    return str(value).strip().lower()


def clean_name(value):
    return re.sub(r"[\s\-@\[\]()]", "", str(value or "")).lower()


# The reviews write solvents as formulae, our table writes them out. Without this every
# cross-source pair fails on the solvent alone.
SOLVENT_SYNONYMS = {
    "eg": "ethyleneglycol", "meg": "ethyleneglycol", "monoethyleneglycol": "ethyleneglycol",
    "ch3oh": "methanol", "meoh": "methanol",
    "deg": "diethyleneglycol", "peg": "polyethyleneglycol",
    "h2o": "water", "nmp": "nmethylpyrrolidone", "dmso": "dimethylsulfoxide",
}


def clean_solvent(value):
    name = clean_name(value)
    return SOLVENT_SYNONYMS.get(name, name)


def close_enough(a, b, slack=0.02):
    if a is None or b is None:
        return a is None and b is None
    if a == 0 and b == 0:
        return True
    return abs(a - b) <= max(abs(a), abs(b)) * slack + 0.01


def name_similarity(left, right):
    a, b = clean_name(left.get("catalyst")), clean_name(right.get("catalyst"))
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def same_experiment(left, right):
    """Two rows describe one experiment.

    The catalyst must be the same substance once notation is stripped. A looser rule merges
    [amim][ZnCl3] with [amim][CoCl3], which differ only by the metal and are different
    experiments; normalised names of genuine variants of one catalyst match exactly.
    """
    a, b = clean_name(left.get("catalyst")), clean_name(right.get("catalyst"))
    if not a or not b or a != b:
        return False
    for field in ("temperature_c", "reaction_time_min"):
        x, y = left.get(field), right.get(field)
        if x is None or y is None or not close_enough(x, y):
            return False
    a_solvent, b_solvent = clean_solvent(left.get("solvent")), clean_solvent(right.get("solvent"))
    if a_solvent and b_solvent and a_solvent != b_solvent:
        return False
    # Conditions identify an experiment. Yield, selectivity and conversion are what the experiment
    # measured, so two sources reporting different outcomes for the same conditions is a
    # disagreement to show the reviewer, not evidence of two different experiments.
    for field in ("catalyst_amount_g", "PET_amount_g", "solvent_amount_g"):
        x, y = left.get(field), right.get(field)
        if x is not None and y is not None and not close_enough(x, y):
            return False
    return True


def tidy(record):
    out = {}
    for field in FIELDS:
        value = record.get(field)
        if value is None or (isinstance(value, float) and pd.isna(value)):
            continue
        if isinstance(value, float) and value == int(value):
            value = int(value)
        out[field] = value
    return out


def cluster_id(doi, cluster):
    """An identifier derived from what the experiment is, not where it landed in a list.

    A positional id (doi#3) silently repoints at a different experiment as soon as a row is added
    or removed anywhere in the paper, which would reattach a reviewer's decisions to the wrong
    records. Hashing the contents means an id survives unrelated edits and disappears only when
    the experiment it names actually changes.
    """
    parts = []
    for member in sorted(cluster, key=lambda m: (m["origin"], json.dumps(m["values"], sort_keys=True))):
        body = "|".join(f"{f}={member['values'].get(f)}" for f in FIELDS)
        parts.append(f"{member['origin']}::{body}")
    raw = doi + "||" + "||".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def fingerprint(cluster):
    values = cluster[0]["values"]
    bits = [str(values.get("catalyst") or "?"),
            f"{values.get('temperature_c')}C",
            f"{values.get('reaction_time_min')}min"]
    for field in ("yield_percent", "selectivity_percent", "conversion_percent"):
        if values.get(field) is not None:
            bits.append(f"{field.split('_')[0]} {values[field]}")
            break
    return " · ".join(bits)


def to_chunks(text):
    parts = re.split(r"^ID: ([0-9a-f-]{36})$", text, flags=re.M)
    return [{"id": parts[i], "html": renderer.render(parts[i + 1])}
            for i in range(1, len(parts), 2)]


source = pd.read_csv(data_path(SOURCE_CSV))
ours = json.loads(data_path(curated_table).read_text())

titles, display_doi = {}, {}
for paper in ours:
    key = doi_key(paper["doi"])
    titles[key] = paper.get("title", "")
    display_doi[key] = paper["doi"]
for row in source.itertuples():
    key = doi_key(row.doi)
    titles.setdefault(key, str(row.title or ""))
    display_doi.setdefault(key, row.doi)

texts = {}
for path in glob.glob(str(data_path("curated_data_markdown_by_doi") / "*.md")):
    texts[doi_key(Path(path).stem.replace("@", "/"))] = Path(path).read_text(encoding="utf-8")

# Every candidate row, tagged with where it came from.
rows_by_doi = {}
for row in source.to_dict("records"):
    label = REVIEW_LABELS.get(doi_key(row.get("source_review_doi")), "review")
    rows_by_doi.setdefault(doi_key(row["doi"]), []).append(
        {"origin": label, "values": tidy(row), "chunks": []})
for paper in ours:
    for entry in paper["extracted_experiments"]:
        data = entry["experiment_data"]
        rows_by_doi.setdefault(doi_key(paper["doi"]), []).append(
            {"origin": "ours", "values": tidy(data),
             "chunks": data.get("source_chunk_ids") or []})

ORDER = ["review A", "review B", "ours"]

payload = {}
for doi, rows in sorted(rows_by_doi.items()):
    # Group rows describing the same experiment. A row joins the first cluster it matches, so a
    # row appearing in both reviews and in our table collapses to a single candidate.
    # Rows are only ever merged across sources, never within one. If a source lists two rows it
    # meant two experiments: this paper's five [amim][ZnCl3] runs at identical conditions are
    # catalyst-recycling cycles, which no schema field distinguishes and no matcher should collapse.
    # A row also has to match every member, so A-B and B-C cannot chain A to C.
    clusters = []
    for row in rows:
        for cluster in clusters:
            if any(member["origin"] == row["origin"] for member in cluster):
                continue
            if all(same_experiment(row["values"], member["values"]) for member in cluster):
                cluster.append(row)
                break
        else:
            clusters.append([row])

    built = []
    used_ids = {}
    for cluster in sorted(clusters, key=lambda c: (
            -len({m["origin"] for m in c}), str(c[0]["values"].get("catalyst", "")))):
        origins = {m["origin"] for m in cluster}
        variants = sorted(cluster, key=lambda m: ORDER.index(m["origin"])
                          if m["origin"] in ORDER else 9)
        # Only real disagreements. [AMIM]Cl against [amim]Cl, or EG against ethylene glycol, is
        # the same answer written differently and should not be flagged for the reviewer.
        # A field only counts as disputed when two sources both recorded it and disagreed. One
        # source leaving it blank is missing coverage, not a conflict.
        def spread(field):
            seen = set()
            for v in variants:
                value = v["values"].get(field)
                if value is None:
                    continue
                if field == "catalyst":
                    seen.add(clean_name(value))
                elif field == "solvent":
                    seen.add(clean_solvent(value))
                else:
                    seen.add(str(value))
            return len(seen) > 1

        disputed = sorted(f for f in FIELDS if spread(f))
        prefer = next((k for k, v in enumerate(variants) if v["origin"] == "ours"), 0)
        # Two clusters can be byte-identical when a paper genuinely repeats a run; the counter
        # keeps their ids apart while staying stable for everything else.
        base = cluster_id(doi, cluster)
        used_ids[base] = used_ids.get(base, 0) + 1
        identifier = base if used_ids[base] == 1 else f"{base}-{used_ids[base]}"

        built.append({
            "id": identifier,
            "label": fingerprint(cluster),
            "origins": [o for o in ORDER if o in origins],
            "inOurs": "ours" in origins,
            "reviewCount": len(origins - {"ours"}),
            "variants": [{"origin": v["origin"], "values": v["values"], "chunks": v["chunks"]}
                         for v in variants],
            "disputed": disputed,
            "prefer": prefer,
            # Default: keep what we already curated, and anything both reviews independently report.
            "suggested": ("ours" in origins) or len(origins - {"ours"}) >= 2,
        })

    payload[doi] = {
        "doi": display_doi.get(doi, doi),
        "title": titles.get(doi, ""),
        "haveText": doi in texts,
        "chunks": to_chunks(texts.get(doi, "")),
        "clusters": built,
    }

all_clusters = [c for p in payload.values() for c in p["clusters"]]


def count(test):
    return sum(1 for c in all_clusters if test(c))


review_rows = {}
for label in ("review A", "review B"):
    doi_for = [k for k, v in REVIEW_LABELS.items() if v == label][0]
    rows = source[source.source_review_doi.str.lower() == doi_for]
    review_rows[label] = (len(rows), rows.doi.str.lower().nunique())

about = f"""
<h2>What this page is for</h2>
<p>We are checking how well our hand-curated experiment table matches the two published reviews it
was originally drawn from, so we can settle on one reference dataset we are confident in.</p>

<h3>Where the data comes from</h3>
<table>
<tr><th>Source</th><th>Experiments</th><th>Papers</th></tr>
<tr><td>Review A <span class="doi">10.1039/d5gc01998b</span></td>
    <td>{review_rows['review A'][0]}</td><td>{review_rows['review A'][1]}</td></tr>
<tr><td>Review B <span class="doi">10.1021/acs.iecr.3c04481</span></td>
    <td>{review_rows['review B'][0]}</td><td>{review_rows['review B'][1]}</td></tr>
<tr class="tot"><td>Both reviews together</td>
    <td>{len(source)}</td><td>{source.doi.str.lower().nunique()}</td></tr>
<tr><td>Our curated table</td><td>{sum(len(p['extracted_experiments']) for p in ours)}</td>
    <td>{len(ours)}</td></tr>
</table>
<p>The two reviews overlap on 16 papers but rarely record the same runs, so their rows mostly add
rather than repeat.</p>

<h3>Putting them side by side</h3>
<p>Those {len(source) + sum(len(p['extracted_experiments']) for p in ours)} rows describe
<b>{len(all_clusters)} distinct experiments</b> across {len(payload)} papers. Rows describing the
same experiment in different sources are merged into one card, matched on catalyst, temperature,
time, solvent and quantities.</p>
<ul>
<li><b>{count(lambda c: len(c['origins']) == 3)}</b> experiments appear in all three sources</li>
<li><b>{count(lambda c: len(c['origins']) == 2)}</b> appear in exactly two</li>
<li><b>{count(lambda c: len(c['origins']) == 1)}</b> appear in only one</li>
</ul>
<p>Relative to our table:</p>
<ul>
<li><b>{count(lambda c: c['inOurs'] and c['reviewCount'])}</b> of our rows also appear in at least
    one review</li>
<li><b>{count(lambda c: c['origins'] == ['ours'])}</b> of our rows appear in neither review</li>
<li><b>{count(lambda c: not c['inOurs'])}</b> experiments appear in the reviews but not in our
    table &mdash; {count(lambda c: not c['inOurs'] and c['reviewCount'] == 2)} of them in both
    reviews independently</li>
<li><b>{count(lambda c: bool(c['disputed']))}</b> experiments have a genuine conflict, where two
    sources record different values for the same run (mostly rounding, such as 90 against 90.3)</li>
</ul>

<h3>What we would like you to do</h3>
<p>The paper's full text is on the left, its experiments on the right. Each card lists every source
reporting that experiment, so you can see at a glance whether it is corroborated. For each one you
can include or exclude it, choose which source's values to trust when they disagree, and correct any
value directly. Clicking <i>find in text</i> highlights that experiment's values in the paper.</p>
<p><b>{count(lambda c: c['suggested'])} entries are pre-selected</b> &mdash; everything already in
our table, plus anything both reviews independently report. The starting point is already a sensible
dataset; the job is correcting it, not building it from nothing.</p>
<p>Your work saves automatically in this browser. <b>Save progress</b> downloads a file you can
reload later with <b>Resume</b>, and <b>Export dataset</b> produces the final table.</p>

<h3>Two things to know before you start</h3>
<p><b>{sum(1 for p in payload.values() if not p['haveText'])} papers have no full text.</b> They
appear in the reviews but were never part of our 24, so their rows cannot be checked against the
paper. Those cards carry a warning, and there is a toggle at the bottom to exclude such a paper
entirely. Deciding what to do with these is itself one of the questions.</p>
<p><b>An unpaired entry is not automatically an error.</b> The two reviews sample different runs
from the same paper, and each writes catalyst names differently. A card marked <i>not in our
set</i> may be a genuine omission or simply an experiment we deliberately left out.</p>
"""

summary = {
    "papers": len(payload),
    "sourceRows": int(len(source)),
    "ourRows": sum(len(p["extracted_experiments"]) for p in ours),
    "candidates": sum(len(p["clusters"]) for p in payload.values()),
    "fields": FIELDS,
}

if __name__ == "__main__":
    page = r"""<!doctype html><html><head><meta charset="utf-8">
    <title>Build the curated dataset</title>
    <style>
     *{box-sizing:border-box}
     body{font:14px/1.55 -apple-system,system-ui,"Segoe UI",sans-serif;margin:0;height:100vh;
       display:flex;flex-direction:column;color:#18202a;background:#f6f7f8}
     header{padding:9px 16px;border-bottom:1px solid #d8dde2;background:#fff;
       display:flex;gap:12px;align-items:center;flex-wrap:wrap}
     header h1{font-size:15px;margin:0;white-space:nowrap;font-weight:650}
     select{padding:5px 7px;font-size:13px;max-width:400px}
     .grow{flex:1}
     .muted{color:#6b7681;font-size:12.5px}
     button{padding:6px 11px;font-size:13px;cursor:pointer;border:1px solid #c3cbd3;
       background:#fff;border-radius:4px}
     button:hover{background:#eef1f4}
     button.primary{background:#0f6b6b;color:#fff;border-color:#0f6b6b}
     button.primary:hover{background:#0d5c5c}
     main{flex:1;display:flex;min-height:0}
     #text{width:46%;overflow-y:auto;padding:15px 19px;border-right:1px solid #d8dde2;
       background:#fff;font-size:12.5px}
     #list{flex:1;overflow-y:auto;padding:13px 16px;min-width:0}
     .chunk{padding:5px 8px;border-left:3px solid transparent;margin:2px 0}
     .chunk table{border-collapse:collapse;margin:7px 0;font-size:11px;display:block;
       overflow-x:auto;max-width:100%}
     .chunk th,.chunk td{border:1px solid #ccc;padding:3px 7px;text-align:left;white-space:nowrap}
     .chunk th{background:#eee}
     .chunk p{margin:4px 0}
     .chunk h1,.chunk h2,.chunk h3{font-size:13px;margin:8px 0 4px}
     .chunk.hit{background:#fff8d6;border-left-color:#e0a800}
     .cid{color:#b3bcc4;font-size:9.5px;user-select:none;display:block}
     mark.val{background:#bfe8e2;border-radius:2px;padding:0 1px}
     mark.cat{background:#ffd9a8;border-radius:2px;padding:0 1px;font-weight:600}
     .cand{border:1px solid #dfe4e8;border-left:4px solid #c3cbd3;border-radius:5px;
       padding:8px 11px;margin-bottom:8px;background:#fff}
     .cand.keep{border-left-color:#2f8f6d;background:#fbfefc}
     .cand.drop{border-left-color:#b8442f;background:#fffafa;opacity:.62}
     .cand.sel{box-shadow:0 0 0 2px #cfe6e4}
     .head{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:5px}
     .head label{display:flex;gap:5px;align-items:center;font-size:12.5px;cursor:pointer}
     .badge{font:10px ui-monospace,Menlo,monospace;text-transform:uppercase;letter-spacing:.05em;
       padding:1px 5px;border-radius:2px;background:#e8edf1;color:#4a5763}
     .badge.a{background:#dfe9f6;color:#2d4f7c}
     .badge.b{background:#e6e2f4;color:#4a3d7a}
     .badge.ours{background:#dcefe5;color:#245f48}
     .badge.warn{background:#f7e6d4;color:#8a4d12}
     .look{margin-left:auto;font-size:11.5px;color:#0f6b6b;cursor:pointer;text-decoration:underline}
     table.vars{border-collapse:collapse;width:100%;font:11.5px ui-monospace,Menlo,monospace}
     table.vars th{text-align:left;font-weight:600;color:#6b7681;padding:2px 5px;
       border-bottom:1px solid #e4e8ec;white-space:nowrap}
     table.vars td{padding:2px 5px;border-bottom:1px solid #f0f2f4;white-space:nowrap}
     table.vars tr.pick td{background:#f2f8f7}
     table.vars td.dis{background:#fdf1e2;font-weight:600}
     .scroll{overflow-x:auto}
     .edit{margin-top:6px;display:none;flex-wrap:wrap;gap:5px}
     .cand.editing .edit{display:flex}
     .edit label{font:10.5px ui-monospace,Menlo,monospace;color:#6b7681;display:flex;
       flex-direction:column;gap:1px}
     .edit input{width:88px;padding:2px 4px;font:11px ui-monospace,Menlo,monospace;
       border:1px solid #c8d0d8;border-radius:3px}
     .edit input.wide{width:190px}
     .warnbox{background:#fdf3e7;border:1px solid #eccfa8;border-radius:4px;padding:8px 11px;
       margin-bottom:10px;font-size:12.5px;color:#7d4b12}
     .hint{background:#eef4f7;border:1px solid #cfdde6;border-radius:4px;padding:7px 10px;
       margin-bottom:9px;font-size:12px;color:#3d5666}
     footer{padding:7px 16px;border-top:1px solid #d8dde2;background:#fff;display:flex;
       gap:10px;align-items:center;flex-wrap:wrap;font-size:13px}
     #shade{position:fixed;inset:0;background:rgba(17,26,34,.45);display:none;z-index:20;
       align-items:flex-start;justify-content:center;padding:36px 20px}
     #shade.open{display:flex}
     #about{background:#fff;border-radius:6px;max-width:760px;width:100%;max-height:100%;
       overflow-y:auto;padding:26px 32px 32px;box-shadow:0 10px 40px rgba(0,0,0,.28);position:relative}
     #about h2{font-size:19px;margin:0 0 10px}
     #about h3{font-size:14.5px;margin:22px 0 7px;padding-bottom:5px;border-bottom:1px solid #e4e8ec}
     #about p{margin:8px 0;font-size:13.5px;line-height:1.62;max-width:64ch}
     #about ul{margin:8px 0;padding-left:20px;font-size:13.5px;line-height:1.7;max-width:64ch}
     #about table{border-collapse:collapse;margin:10px 0;font-size:13px}
     #about th{text-align:left;font-weight:600;color:#6b7681;padding:4px 16px 4px 0;
       border-bottom:1px solid #d8dde2}
     #about td{padding:4px 16px 4px 0;border-bottom:1px solid #eef1f4;
       font-variant-numeric:tabular-nums}
     #about tr.tot td{font-weight:650;border-bottom:2px solid #d8dde2}
     #about .doi{font:11px ui-monospace,Menlo,monospace;color:#8b96a1}
     #close{position:absolute;top:10px;right:12px;border:none;background:none;font-size:24px;
       line-height:1;color:#8b96a1;cursor:pointer;padding:4px 9px}
     #close:hover{color:#18202a;background:none}
     #note{flex:1;min-width:200px;padding:5px 7px;font-size:13px;border:1px solid #c3cbd3;border-radius:4px}
    </style></head><body>
    <header>
      <h1>Build the curated dataset</h1>
      <select id="pick"></select>
      <span class="muted" id="paperStat"></span>
      <span class="grow"></span>
      <label class="muted"><input type="checkbox" id="allVals"> highlight all values</label>
      <span class="muted" id="progress"></span>
      <button onclick="openAbout()">About this review</button>
      <button onclick="document.getElementById('load').click()">Resume</button>
      <input type="file" id="load" accept=".json" hidden>
      <button onclick="saveDecisions()">Save progress</button>
      <button class="primary" onclick="saveDataset()">Export dataset</button>
    </header>
    <main>
      <div id="text"></div>
      <div id="list"></div>
    </main>
    <div id="shade"><div id="about"><button id="close" title="close">&times;</button></div></div>
    <footer>
      <span class="muted">Paper note:</span>
      <input id="note" placeholder="anything worth recording about this paper">
      <label class="muted"><input type="checkbox" id="skip"> exclude this paper entirely</label>
    </footer>
    <script>
    const DATA = __DATA__;
    const SUMMARY = __SUMMARY__;
    const FIELDS = SUMMARY.fields;
    const STORE = 'curationDecisions.v2';

    let state = load();
    let current = null;

    function load(){
      // Decisions saved before ids became content-derived name positions that no longer exist, so the
      // old key is discarded rather than carried into new exports.
      try { localStorage.removeItem('curationDecisions.v1'); } catch (e) {}
      try { return JSON.parse(localStorage.getItem(STORE)) || {clusters:{}, papers:{}}; }
      catch (e) { return {clusters:{}, papers:{}}; }
    }
    function persist(){
      try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (e) {}
      progress();
    }
    // Reading a candidate must not record a decision about it. Writing on render made merely opening
    // a paper look like 20 decisions, so a saved file could not be told apart from an untouched one.
    function settings(c){
      return state.clusters[c.id] || {keep: c.suggested, variant: c.prefer, edits: null};
    }
    function decide(c, patch){
      state.clusters[c.id] = Object.assign(settings(c), patch);
      persist();
    }

    const dois = Object.keys(DATA).sort();
    const pick = document.getElementById('pick');
    dois.forEach(d => pick.add(new Option(
      DATA[d].doi + '   (' + DATA[d].clusters.length + ' candidates)', d)));

    function esc(s){
      return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
    }

    function finalValues(c){
      const d = settings(c);
      return Object.assign({}, c.variants[d.variant].values, d.edits || {});
    }

    function progress(){
      let kept = 0, decided = 0, total = 0;
      dois.forEach(d => {
        if ((state.papers[d] || {}).skip) return;
        DATA[d].clusters.forEach(c => {
          total++;
          if (state.clusters[c.id]) decided++;
          if ((state.clusters[c.id] || {keep: c.suggested}).keep) kept++;
        });
      });
      document.getElementById('progress').textContent =
        kept + ' rows selected · ' + decided + ' of ' + total + ' touched';
    }

    /* ---------- text highlighting ---------- */
    function clearMarks(){
      document.querySelectorAll('#text mark').forEach(m => {
        m.parentNode.replaceChild(document.createTextNode(m.textContent), m);
      });
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
      const root = document.getElementById('text');
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
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
    function paintAll(){
      const seen = new Set();
      DATA[current].clusters.forEach(c => terms(finalValues(c)).forEach(t => seen.add(t)));
      paint([...seen], 'val');
    }
    function highlight(c){
      clearMarks();
      document.querySelectorAll('.chunk').forEach(e => e.classList.remove('hit'));
      const values = finalValues(c);
      c.variants.forEach(v => (v.chunks || []).forEach(id => {
        const el = document.getElementById('k_' + id);
        if (el) el.classList.add('hit');
      }));
      const cat = String(values.catalyst || '').trim();
      if (cat.length >= 3) paint([cat.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')], 'cat');
      paint(terms(values), 'val');
      const first = document.querySelector('.chunk.hit') || document.querySelector('#text mark');
      if (first) first.scrollIntoView({block:'center', behavior:'smooth'});
    }

    /* ---------- candidate rendering ---------- */
    function badge(text, cls){
      const s = document.createElement('span');
      s.className = 'badge ' + (cls || '');
      s.textContent = text;
      return s;
    }

    function candidateEl(c){
      const d = settings(c);
      const box = document.createElement('div');
      box.className = 'cand ' + (d.keep ? 'keep' : 'drop');
      box.dataset.id = c.id;

      const head = document.createElement('div');
      head.className = 'head';

      const keepLabel = document.createElement('label');
      const keep = document.createElement('input');
      keep.type = 'checkbox';
      keep.checked = d.keep;
      keep.addEventListener('change', () => {
        decide(c, {keep: keep.checked});
        box.classList.toggle('keep', keep.checked);
        box.classList.toggle('drop', !keep.checked);
      });
      keepLabel.appendChild(keep);
      keepLabel.appendChild(document.createTextNode('include'));
      head.appendChild(keepLabel);

      c.origins.forEach(o => head.appendChild(
        badge(o, o === 'ours' ? 'ours' : (o === 'review A' ? 'a' : 'b'))));
      if (!c.inOurs) head.appendChild(badge('not in our set', 'warn'));
      if (c.disputed.length) head.appendChild(badge(c.disputed.length + ' fields differ', 'warn'));

      const look = document.createElement('span');
      look.className = 'look';
      look.textContent = 'find in text';
      look.addEventListener('click', e => {
        e.stopPropagation();
        document.querySelectorAll('.cand.sel').forEach(x => x.classList.remove('sel'));
        box.classList.add('sel');
        highlight(c);
      });
      head.appendChild(look);
      box.appendChild(head);

      const scroll = document.createElement('div');
      scroll.className = 'scroll';
      const table = document.createElement('table');
      table.className = 'vars';
      const shown = FIELDS.filter(f => c.variants.some(v => v.values[f] !== undefined));
      const header = document.createElement('tr');
      header.appendChild(document.createElement('th'));
      ['source'].concat(shown).forEach(name => {
        const th = document.createElement('th');
        th.textContent = name.replace('_percent','').replace('_c','').replace('_min','').replace('_g','');
        header.appendChild(th);
      });
      table.appendChild(header);

      c.variants.forEach((v, i) => {
        const tr = document.createElement('tr');
        if (i === d.variant) tr.className = 'pick';
        const cell = document.createElement('td');
        const radio = document.createElement('input');
        radio.type = 'radio';
        radio.name = 'v_' + c.id;
        radio.checked = i === d.variant;
        radio.addEventListener('change', () => {
          decide(c, {variant: i, edits: null});
          box.replaceWith(candidateEl(c));
        });
        cell.appendChild(radio);
        tr.appendChild(cell);
        const origin = document.createElement('td');
        origin.textContent = v.origin;
        tr.appendChild(origin);
        shown.forEach(f => {
          const td = document.createElement('td');
          if (c.disputed.includes(f)) td.className = 'dis';
          td.textContent = v.values[f] === undefined ? '—' : v.values[f];
          tr.appendChild(td);
        });
        table.appendChild(tr);
      });
      scroll.appendChild(table);
      box.appendChild(scroll);

      const editToggle = document.createElement('span');
      editToggle.className = 'look';
      editToggle.style.marginLeft = '0';
      editToggle.textContent = 'edit values';
      editToggle.addEventListener('click', () => box.classList.toggle('editing'));
      box.appendChild(editToggle);

      const edit = document.createElement('div');
      edit.className = 'edit';
      const values = finalValues(c);
      FIELDS.forEach(f => {
        const label = document.createElement('label');
        label.textContent = f;
        const input = document.createElement('input');
        if (f === 'catalyst' || f === 'solvent') input.className = 'wide';
        input.value = values[f] === undefined ? '' : values[f];
        input.addEventListener('input', () => {
          const edits = Object.assign({}, settings(c).edits || {});
          const raw = input.value.trim();
          if (raw === '') delete edits[f];
          else edits[f] = (f === 'catalyst' || f === 'solvent' || isNaN(Number(raw)))
            ? raw : Number(raw);
          decide(c, {edits: Object.keys(edits).length ? edits : null});
        });
        label.appendChild(input);
        edit.appendChild(label);
      });
      box.appendChild(edit);
      return box;
    }

    function show(doi){
      current = doi;
      const paper = DATA[doi];
      const text = document.getElementById('text');
      if (paper.haveText){
        text.innerHTML = paper.chunks.map(c =>
          '<div class="chunk" id="k_' + c.id + '"><span class="cid">' + c.id + '</span>' + c.html
          + '</div>').join('');
      } else {
        text.innerHTML = '<div class="warnbox"><b>No full text for this paper.</b> It appears in the '
          + 'source reviews but was never part of our 24, so its rows cannot be checked against the '
          + 'paper here. Either exclude the paper, or add its text before deciding.</div>';
      }

      const list = document.getElementById('list');
      list.innerHTML = '';

      const hint = document.createElement('div');
      hint.className = 'hint';
      hint.textContent = 'One card per experiment. Rows describing the same experiment in different '
        + 'sources are merged, so a card carrying several badges is one experiment reported more than '
        + 'once, not a duplicate. Orange cells are fields the sources disagree on — choose which '
        + 'source to trust, or edit the values directly.';
      list.appendChild(hint);

      const settings = state.papers[doi] || {};
      document.getElementById('note').value = settings.note || '';
      document.getElementById('skip').checked = !!settings.skip;

      paper.clusters.forEach(c => list.appendChild(candidateEl(c)));

      const inOurs = paper.clusters.filter(c => c.inOurs).length;
      const newOnes = paper.clusters.length - inOurs;
      document.getElementById('paperStat').textContent =
        paper.clusters.length + ' candidates · ' + inOurs + ' already ours · '
        + newOnes + ' only in the reviews';

      if (document.getElementById('allVals').checked) paintAll();
      text.scrollTop = 0;
      progress();
    }

    document.getElementById('note').addEventListener('input', e => {
      state.papers[current] = Object.assign({}, state.papers[current], {note: e.target.value});
      persist();
    });
    document.getElementById('skip').addEventListener('change', e => {
      state.papers[current] = Object.assign({}, state.papers[current], {skip: e.target.checked});
      persist();
    });
    document.getElementById('allVals').addEventListener('change', () => {
      clearMarks();
      if (document.getElementById('allVals').checked) paintAll();
    });
    pick.addEventListener('change', () => show(pick.value));

    /* ---------- saving ---------- */
    function download(name, text){
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([text], {type:'application/json'}));
      a.download = name;
      a.click();
    }
    function saveDecisions(){
      // Each decision carries a plain-language fingerprint of the experiment it refers to, so a file
      // can be read by a human and checked against the data it was recorded on.
      const labels = {};
      dois.forEach(d => DATA[d].clusters.forEach(c => {
        if (state.clusters[c.id]) labels[c.id] = DATA[d].doi + '  ' + c.label;
      }));
      download('curation_decisions.json',
               JSON.stringify({version: 2, refersTo: labels,
                               clusters: state.clusters, papers: state.papers}, null, 2));
    }
    function saveDataset(){
      const papers = [];
      let kept = 0;
      dois.forEach(d => {
        if ((state.papers[d] || {}).skip) return;
        const rows = DATA[d].clusters.filter(c => settings(c).keep).map(c => {
          const values = finalValues(c);
          const chunks = [];
          c.variants.forEach(v => (v.chunks || []).forEach(x => {
            if (!chunks.includes(x)) chunks.push(x);
          }));
          const experiment = {};
          FIELDS.forEach(f => { experiment[f] = values[f] === undefined ? null : values[f]; });
          experiment.source_chunk_ids = chunks;
          return {experiment_data: experiment};
        });
        kept += rows.length;
        if (rows.length) papers.push({doi: DATA[d].doi, title: DATA[d].title,
                                      extracted_experiments: rows});
      });
      download('curated_table_reviewed.json', JSON.stringify(papers, null, 2));
      alert('Exported ' + kept + ' experiments across ' + papers.length + ' papers.\n\n'
            + 'Save progress separately if you want to carry on editing later.');
    }
    document.getElementById('load').addEventListener('change', e => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const loaded = JSON.parse(reader.result);
          const incoming = loaded.clusters || {};
          const known = new Set();
          dois.forEach(d => DATA[d].clusters.forEach(c => known.add(c.id)));
          const orphans = Object.keys(incoming).filter(k => !known.has(k));
          state = {clusters: incoming, papers: loaded.papers || {}};
          persist();
          show(current);
          const kept = Object.keys(incoming).length - orphans.length;
          let message = 'Loaded ' + kept + ' decisions.';
          if (orphans.length){
            message += '\n\n' + orphans.length + ' no longer match any experiment. The underlying '
              + 'data has changed since they were recorded, so those experiments need deciding '
              + 'again. They were NOT applied to anything else.';
            if (loaded.refersTo){
              message += '\n\nFirst few:\n' + orphans.slice(0, 5)
                .map(k => '  ' + (loaded.refersTo[k] || k)).join('\n');
            }
          }
          alert(message);
        } catch (err) { alert('Could not read that file.'); }
      };
      reader.readAsText(file);
    });

    const ABOUT = __ABOUT__;
    const shade = document.getElementById('shade');
    document.getElementById('about').insertAdjacentHTML('beforeend', ABOUT);
    function openAbout(){ shade.classList.add('open'); }
    function closeAbout(){ shade.classList.remove('open'); }
    document.getElementById('close').addEventListener('click', closeAbout);
    shade.addEventListener('click', e => { if (e.target === shade) closeAbout(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeAbout(); });

    show(dois[0]);
    progress();
    </script></body></html>
    """

    page = (page.replace("__DATA__", json.dumps(payload))
            .replace("__SUMMARY__", json.dumps(summary))
            .replace("__ABOUT__", json.dumps(about)))
    out = ARTIFACTS / "curation_review.html"
    out.write_text(page, encoding="utf-8")

    merged = sum(1 for p in payload.values() for c in p["clusters"] if len(c["origins"]) > 1)
    ours_only = sum(1 for p in payload.values() for c in p["clusters"] if c["origins"] == ["ours"])
    reviews_only = sum(1 for p in payload.values() for c in p["clusters"] if not c["inOurs"])
    disputed = sum(1 for p in payload.values() for c in p["clusters"] if c["disputed"])
    no_text = [d for d, p in payload.items() if not p["haveText"]]

    print(f"wrote {out}  ({out.stat().st_size // 1024} KB)")
    print(f"papers                                {summary['papers']}")
    print(f"rows in                               {summary['sourceRows']} review + {summary['ourRows']} ours")
    print(f"distinct candidate experiments        {summary['candidates']}")
    print(f"  reported by more than one source    {merged}")
    print(f"  only in our table                   {ours_only}")
    print(f"  only in the reviews                 {reviews_only}")
    print(f"  with fields the sources dispute     {disputed}")
    print(f"papers with no full text              {len(no_text)}")
