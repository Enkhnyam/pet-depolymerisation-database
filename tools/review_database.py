"""Build a self-contained HTML review page for an extraction and the judge's verdicts on it.

One page per extraction/judge pair. Every record is shown with its fields, the judge's verdict
and reasoning, any corrections the judge proposed, and the source text the record cites -- with
the extracted values highlighted inside it, so a reader can check a number against the sentence
it came from without opening the paper.

The page carries both versions of the data. A toggle switches every corrected field between the
value the extractor wrote and the value the judge proposed, so the corrected database can be
reviewed without generating a second file.

    review_database.py --extraction mass_luna --judge mass_oss/mass_oss
    review_database.py --extraction smoke --judge smoke_judge/smoke_judge --out /tmp/smoke.html

Any extraction and judge run work, whatever models produced them, as long as the judge ran
against that extraction.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root importable
from core.paths import ARTIFACTS, RUNS_DIR, data_path
from core.utils import doi_to_filename

FIELDS = ["catalyst", "solvent", "temperature_c", "reaction_time_min", "catalyst_amount_g",
          "PET_amount_g", "solvent_amount_g", "yield_percent", "selectivity_percent",
          "conversion_percent", "pressure_atm"]

LABELS = {"catalyst": "catalyst", "solvent": "solvent", "temperature_c": "temp (°C)",
          "reaction_time_min": "time (min)", "catalyst_amount_g": "catalyst (g)",
          "PET_amount_g": "PET (g)", "solvent_amount_g": "solvent (g)",
          "yield_percent": "yield (%)", "selectivity_percent": "selectivity (%)",
          "conversion_percent": "conversion (%)", "pressure_atm": "pressure (atm)"}

CHUNK_PATTERN = re.compile(r"^ID: ([0-9a-f-]{36})$", re.M)


def load_run(run_dir: Path, subdir: str) -> dict:
    """Every JSON file in a run subdirectory, keyed by the doi it records."""
    by_doi = {}
    for path in sorted((run_dir / subdir).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        by_doi[payload["doi"]] = payload
    return by_doi


def load_chunks(markdown_dir: Path, doi: str) -> dict:
    """Split a paper's markdown into {chunk id: text}, the form source_chunk_ids points at."""
    path = markdown_dir / doi_to_filename(doi.lower(), "md")
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    pieces = CHUNK_PATTERN.split(text)
    # split() yields [preamble, id, body, id, body, ...]
    return {pieces[i]: pieces[i + 1].strip() for i in range(1, len(pieces) - 1, 2)}


def paper_title(chunks: dict) -> str:
    """The first non-empty line of the paper, which the parser puts the title on."""
    for body in chunks.values():
        for line in body.splitlines():
            cleaned = line.strip().lstrip("#").strip()
            if len(cleaned) > 20:
                return cleaned
    return ""


def value_forms(value) -> list[str]:
    """The ways a value might literally appear in the paper's text."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if len(value) > 2 else []

    forms = {f"{value:g}"}
    if float(value).is_integer():
        forms.add(str(int(value)))
    else:
        forms.add(f"{value:.1f}".rstrip("0").rstrip("."))
    return [form for form in forms if len(form) > 1]


def highlight(text: str, record: dict) -> str:
    """Escape chunk text, then mark every extracted value that appears in it."""
    escaped = html.escape(text)

    wanted = []
    for field in FIELDS:
        for form in value_forms(record.get(field)):
            wanted.append((form, field))
    # longest first, so "100" inside "100.5" does not win over the fuller match
    wanted.sort(key=lambda pair: -len(pair[0]))

    for form, field in wanted:
        pattern = re.compile(rf"(?<![\w.]){re.escape(html.escape(form))}(?![\w.])")
        escaped, _ = pattern.subn(
            f'<mark class="v" data-field="{field}">{html.escape(form)}</mark>', escaped, count=3)
    return escaped


def render_value(value) -> str:
    if value is None:
        return '<span class="null">not reported</span>'
    if isinstance(value, float) and value.is_integer():
        return html.escape(str(int(value)))
    return html.escape(str(value))


def render_record(record: dict, verdict: dict, chunks: dict, index: int) -> str:
    """One record: its fields, the verdict, the reasoning, and the text it cites."""
    fixes = {fix["field"]: fix for fix in (verdict.get("fixes") or [])}
    bad = set(verdict.get("bad_fields") or [])
    passed = verdict.get("verdict") == "correct"
    dropped = verdict.get("drop_record")

    state = "ok" if passed else ("drop" if dropped else "fixed")
    label = {"ok": "accepted", "drop": "judge would drop", "fixed": "corrected"}[state]

    cells = []
    for field in FIELDS:
        original = record.get(field)
        classes = ["cell"]
        if field in bad:
            classes.append("bad")

        shown = f'<span class="orig">{render_value(original)}</span>'
        if field in fixes:
            shown += f'<span class="fix">{render_value(fixes[field]["value"])}</span>'
            classes.append("has-fix")

        cells.append(f'<div class="{" ".join(classes)}">'
                     f'<span class="k">{LABELS[field]}</span>{shown}</div>')

    cited = record.get("source_chunk_ids") or []
    sources = []
    for chunk_id in cited:
        body = chunks.get(chunk_id)
        if body is None:
            sources.append(f'<div class="src missing">cited chunk not found: '
                           f'<code>{html.escape(chunk_id)}</code></div>')
            continue
        sources.append(f'<div class="src"><code class="cid">{html.escape(chunk_id[:8])}</code>'
                       f'<div class="txt">{highlight(body, record)}</div></div>')
    if not cited:
        sources.append('<div class="src missing">this record cites no source chunk</div>')

    evidence = ""
    if fixes:
        items = "".join(
            f"<li><b>{LABELS.get(f, f)}</b>: {render_value(record.get(f))} &rarr; "
            f"{render_value(fix['value'])}<br><span class='ev'>"
            f"{html.escape(fix.get('evidence') or '')}</span></li>"
            for f, fix in fixes.items())
        evidence = f'<ul class="fixes">{items}</ul>'

    critique = html.escape(verdict.get("critique") or "")
    return f"""<div class="rec {state}" data-state="{state}">
  <div class="rechead"><span class="idx">#{index}</span>
    <span class="badge {state}">{label}</span></div>
  <div class="grid">{"".join(cells)}</div>
  {f'<p class="crit">{critique}</p>' if critique else ""}
  {evidence}
  <details class="sources"><summary>{len(cited)} source chunk{"" if len(cited) == 1 else "s"}</summary>
    {"".join(sources)}</details>
</div>"""


def render_paper(doi: str, records: list, verdicts: dict, chunks: dict) -> str:
    title = paper_title(chunks)
    blocks = [render_record(record, verdicts.get(i, {}), chunks, i)
              for i, record in enumerate(records)]

    fixed = sum(1 for i in range(len(records))
                if (verdicts.get(i, {}).get("fixes") or []))
    passed = sum(1 for i in range(len(records))
                 if verdicts.get(i, {}).get("verdict") == "correct")
    summary = (f'<span class="n">{len(records)} records</span>'
               f'<span class="n ok">{passed} accepted</span>'
               f'<span class="n fixed">{fixed} corrected</span>')

    return f"""<details class="paper">
  <summary><span class="doi">{html.escape(doi)}</span>
    <span class="title">{html.escape(title)}</span>{summary}</summary>
  {"".join(blocks)}
</details>"""


def build(extraction: Path, judge: Path | None, markdown_dir: Path, title: str) -> str:
    extractions = load_run(extraction, "extractions")
    verdicts_by_doi = load_run(judge, "verdicts") if judge else {}

    total = corrected = accepted = dropped = 0
    sections = []
    for doi in sorted(extractions):
        records = extractions[doi]["records"]
        if not records:
            continue
        payload = verdicts_by_doi.get(doi, {})
        verdicts = {v["extracted_index"]: v for v in payload.get("verdicts", [])}

        total += len(records)
        for i in range(len(records)):
            verdict = verdicts.get(i, {})
            if verdict.get("verdict") == "correct":
                accepted += 1
            elif verdict.get("drop_record"):
                dropped += 1
            elif verdict.get("fixes"):
                corrected += 1

        chunks = load_chunks(markdown_dir, doi)
        sections.append(render_paper(doi, records, verdicts, chunks))

    papers = len(sections)
    rate = f"{accepted / total:.1%}" if total else "n/a"
    stats = [("papers", papers), ("records", total), ("accepted", accepted),
             ("corrected", corrected), ("would drop", dropped), ("pass rate", rate)]
    tiles = "".join(f'<div class="tile"><span class="num">{v}</span>'
                    f'<span class="lab">{k}</span></div>' for k, v in stats)

    return TEMPLATE.format(title=html.escape(title), tiles=tiles,
                           extraction=html.escape(extraction.name),
                           judge=html.escape(judge.name if judge else "none"),
                           sections="\n".join(sections))


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#f4f6f6;--card:#fff;--ink:#16211f;--dim:#5d716e;--line:#dbe4e2;
  --ok:#3f6e46;--ok-bg:#e4efe4;--fix:#9a6510;--fix-bg:#f7ecd9;--drop:#a33a2e;--drop-bg:#f8e3de;
  --mark:#ffe9a8;--accent:#0e7c6b}}
@media(prefers-color-scheme:dark){{:root{{--bg:#0d1514;--card:#141f1e;--ink:#dee8e5;--dim:#93a7a4;
  --line:#263634;--ok:#7fb187;--ok-bg:#16281a;--fix:#d6a054;--fix-bg:#2c2413;--drop:#d98374;
  --drop-bg:#2e1a16;--mark:#5a4a1a;--accent:#4fc4ae}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 ui-sans-serif,system-ui,sans-serif}}
.wrap{{max-width:1080px;margin:0 auto;padding:28px 20px 80px}}
h1{{font-size:1.6rem;margin:0 0 6px}}
.sub{{color:var(--dim);margin:0 0 22px;font-size:.92rem}}
.tiles{{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:22px}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 16px;min-width:104px}}
.tile .num{{display:block;font-size:1.5rem;font-weight:600;font-variant-numeric:tabular-nums}}
.tile .lab{{display:block;color:var(--dim);font-size:.76rem;text-transform:uppercase;letter-spacing:.07em}}
.bar{{display:flex;gap:10px;flex-wrap:wrap;align-items:center;position:sticky;top:0;z-index:5;
  background:var(--bg);padding:10px 0;border-bottom:1px solid var(--line);margin-bottom:18px}}
input,select,button{{font:inherit;padding:7px 10px;border:1px solid var(--line);border-radius:6px;
  background:var(--card);color:var(--ink)}}
input{{flex:1;min-width:200px}}
button{{cursor:pointer}}
button.on{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.paper{{background:var(--card);border:1px solid var(--line);border-radius:8px;margin-bottom:10px}}
.paper>summary{{cursor:pointer;padding:13px 16px;display:flex;gap:12px;flex-wrap:wrap;align-items:baseline}}
.paper>summary::marker{{color:var(--dim)}}
.doi{{font-family:ui-monospace,monospace;font-size:.84rem;color:var(--accent)}}
.title{{flex:1;min-width:200px;color:var(--dim);font-size:.9rem}}
.n{{font-size:.76rem;color:var(--dim);white-space:nowrap}}
.n.ok{{color:var(--ok)}} .n.fixed{{color:var(--fix)}}
.rec{{border-top:1px solid var(--line);padding:14px 16px}}
.rechead{{display:flex;gap:10px;align-items:center;margin-bottom:9px}}
.idx{{font-family:ui-monospace,monospace;color:var(--dim);font-size:.8rem}}
.badge{{font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;padding:3px 8px;border-radius:4px}}
.badge.ok{{background:var(--ok-bg);color:var(--ok)}}
.badge.fixed{{background:var(--fix-bg);color:var(--fix)}}
.badge.drop{{background:var(--drop-bg);color:var(--drop)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(148px,1fr));gap:7px;margin-bottom:10px}}
.cell{{background:var(--bg);border:1px solid var(--line);border-radius:5px;padding:6px 9px;font-size:.86rem}}
.cell .k{{display:block;color:var(--dim);font-size:.68rem;text-transform:uppercase;letter-spacing:.05em}}
.cell.bad{{border-color:var(--fix);background:var(--fix-bg)}}
.null{{color:var(--dim);font-style:italic;font-size:.85em}}
.fix{{display:none}}
body.corrected .has-fix .orig{{display:none}}
body.corrected .has-fix .fix{{display:inline;font-weight:600;color:var(--fix)}}
.crit{{margin:0 0 10px;font-size:.9rem;color:var(--dim);border-left:2px solid var(--line);padding-left:11px}}
.fixes{{margin:0 0 10px;padding-left:18px;font-size:.87rem}}
.fixes li{{margin-bottom:6px}}
.ev{{color:var(--dim);font-size:.9em}}
.sources summary{{cursor:pointer;color:var(--dim);font-size:.82rem}}
.src{{margin-top:9px;border-left:2px solid var(--line);padding-left:11px}}
.src.missing{{color:var(--drop);font-size:.84rem}}
.cid{{font-size:.72rem;color:var(--dim)}}
.txt{{white-space:pre-wrap;font-size:.84rem;color:var(--dim);max-height:230px;overflow:auto;margin-top:4px}}
mark.v{{background:var(--mark);color:var(--ink);border-radius:2px;padding:0 2px}}
.hidden{{display:none}}
</style></head><body>
<div class="wrap">
<h1>{title}</h1>
<p class="sub">extraction <code>{extraction}</code> &middot; judge <code>{judge}</code>.
Values highlighted in the source text are the ones this record claims. Open a paper to review it.</p>
<div class="tiles">{tiles}</div>
<div class="bar">
  <input id="q" placeholder="filter by DOI or catalyst…">
  <select id="state">
    <option value="">all records</option>
    <option value="ok">accepted only</option>
    <option value="fixed">corrected only</option>
    <option value="drop">would drop only</option>
  </select>
  <button id="toggle">show corrected values</button>
  <button id="expand">expand all</button>
</div>
{sections}
</div>
<script>
const papers = [...document.querySelectorAll('.paper')];
const q = document.getElementById('q'), state = document.getElementById('state');

function apply() {{
  const needle = q.value.toLowerCase().trim(), want = state.value;
  for (const paper of papers) {{
    const recs = [...paper.querySelectorAll('.rec')];
    let shown = 0;
    for (const rec of recs) {{
      const okState = !want || rec.dataset.state === want;
      const okText = !needle || paper.querySelector('.doi').textContent.toLowerCase().includes(needle)
                     || rec.textContent.toLowerCase().includes(needle);
      const visible = okState && okText;
      rec.classList.toggle('hidden', !visible);
      if (visible) shown++;
    }}
    paper.classList.toggle('hidden', shown === 0);
  }}
}}
q.addEventListener('input', apply);
state.addEventListener('change', apply);

document.getElementById('toggle').addEventListener('click', e => {{
  const on = document.body.classList.toggle('corrected');
  e.target.classList.toggle('on', on);
  e.target.textContent = on ? 'showing corrected values' : 'show corrected values';
}});
document.getElementById('expand').addEventListener('click', e => {{
  const on = e.target.classList.toggle('on');
  papers.forEach(p => {{ if (!p.classList.contains('hidden')) p.open = on; }});
  e.target.textContent = on ? 'collapse all' : 'expand all';
}});
</script>
</body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(prog="review_database")
    parser.add_argument("--extraction", required=True,
                        help="extraction run under artifacts/runs, e.g. mass_luna")
    parser.add_argument("--judge", default=None,
                        help="judge run under artifacts/runs, e.g. mass_oss/mass_oss")
    parser.add_argument("--corpus", default="corpus_markdown",
                        help="chunked markdown directory under artifacts/data")
    parser.add_argument("--out", default=None, help="output HTML path")
    parser.add_argument("--title", default="PET depolymerisation database — record review")
    args = parser.parse_args()

    extraction = RUNS_DIR / args.extraction
    judge = RUNS_DIR / args.judge if args.judge else None
    if not (extraction / "extractions").is_dir():
        parser.error(f"no extractions/ in {extraction}")
    if judge and not (judge / "verdicts").is_dir():
        parser.error(f"no verdicts/ in {judge}")

    page = build(extraction, judge, data_path(args.corpus), args.title)
    out = Path(args.out) if args.out else ARTIFACTS / f"review_{args.extraction.replace('/', '_')}.html"
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
