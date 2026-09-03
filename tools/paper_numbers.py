"""Emit every number the papers quote as LaTeX macros, from one pass over the checks.

A reviewer found the manuscripts irreconcilable: 5,563 records in the abstract against 2,128 in a
table whose rows summed to 4,402; 664 papers in one section and 285 in another; citation
resolution quoted twice at 96.5% and 93.6%; an adjudication of 112 records in the results and 48
in the limitations. Every one of those came from the same cause -- a literal typed into the
manuscript by hand, correct on the day, never revisited when the run behind it changed. Patching
them individually is how the drift happened in the first place, and it made at least one table
worse rather than better.

So the numbers stop being typed. This writes artifacts/paper_numbers.tex, a file of
\\newcommand definitions computed from the checks, and both manuscripts \\input it and cite the
macros. A number can then be wrong -- if a check is wrong -- but it cannot be *inconsistent*,
because there is only one of it.

It also writes a provenance block: the runs every number came from and a hash over their
config.json content hashes, so the paper can name the exact artifact set it describes. Change a
run and the hash changes; the paper then declares a different artifact and the mismatch is
visible rather than silent.

    paper_numbers.py                 write the macros
    paper_numbers.py --check         fail if the file on disk is stale (for CI)
"""
import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "checks"))
sys.path.insert(0, str(ROOT / "tools"))

from core.paths import ARTIFACTS
from macro_derivations import DERIVATION
import _setup
from curated import extractions, shots, source_tracking, thresholds
from database import chemistry, corpus, provenance, verdicts
from human import adjudicated, integrity, worklist

OUT = ARTIFACTS / "paper_numbers.tex"
FIELD_TABLE = ARTIFACTS / "paper_table_fields.tex"
MATRIX_TABLE = ARTIFACTS / "paper_table_matrix.tex"

# Schema field -> how the manuscripts name it.
FIELD_LABELS = {
    "catalyst_amount_g": "catalyst mass (g)", "solvent_amount_g": "solvent mass (g)",
    "PET_amount_g": "PET mass (g)", "temperature_c": "temperature (\\textdegree C)",
    "reaction_time_min": "reaction time (min)", "yield_percent": "yield (\\%)",
    "conversion_percent": "conversion (\\%)", "selectivity_percent": "selectivity (\\%)",
    "pressure_atm": "pressure (atm)", "catalyst": "catalyst", "solvent": "solvent",
}
RESOLVED_KEY = "resolve to the paper's own text"

# \AdjPowerAt70 is not a legal control sequence, so the rates are spelled out.
WORDS = {60: "Sixty", 65: "SixtyFive", 70: "Seventy", 75: "SeventyFive", 80: "Eighty"}

# The macro names are deliberately verbose: \DatabaseRecords is unmistakable in a manuscript in a
# way that \NR is not, and the point of this file is that a reader of the .tex can see where a
# number came from.
def collect() -> tuple[dict, dict]:
    co, ch, ve, pr = corpus.compute(), chemistry.compute(), verdicts.compute(), provenance.compute()
    ex = extractions.arms()
    sh = shots.compute()
    contrast = shots.contrast(sh)
    src = source_tracking.compute()
    sweeps = thresholds.compute()
    audit = adjudicated.compute(adjudicated.REAL)
    table, mcnemar = audit["table"], audit["mcnemar"]
    counts, funnel = ve["counts"], co["funnel"]
    routes = ch["by route"]["records"]
    identity = ch["identity"]
    curated_rows = _setup.curated()
    integ = integrity.compute()
    decided_fresh = _decided_fresh()
    from curated import matrix as _matrix
    mx = _matrix.compute()
    mx_ship = mx[(mx.judge == "oss") & (mx.extraction == "luna")].iloc[0]
    from curated import extractions as _ex
    import cost as _cost
    _runs, _ledger = _ex.runs(), _cost.compute().set_index("run")
    def _arm_cost(model):
        arm = _runs[(_runs.model == model) & (_runs.n_shots == int(ex.loc[model, "n_shots"]))]
        vals = [_ledger.loc[k, "cost_usd"] for n in arm.run for k in _ledger.index if k.endswith("/" + n)]
        return sum(vals) / len(vals) if vals else float("nan")
    cost_luna, cost_terra = _arm_cost("luna"), _arm_cost("terra")
    database_meta = json.loads((_setup.DATABASE / "run_meta.json").read_text())
    from itertools import combinations as _comb
    from scipy.stats import ttest_ind as _tt
    _arms = [n for n in sorted(sh.n_shots.unique()) if n > 0]
    _pairs = list(_comb(_arms, 2))
    shots_comparisons = len(_pairs)
    shots_smallest_pairwise = min(
        _tt(sh.query("n_shots == @a").f1, sh.query("n_shots == @b").f1).pvalue
        for a, b in _pairs)
    from database import withinpaper
    within_lead = withinpaper.compute()["table"].loc["hotter gives more"]
    import glob as _glob
    from core.paths import data_path as _dp
    largest_judged = max(
        ((_dp("corpus_markdown") / (json.loads(open(f).read())["doi"].replace("/", "@").lower() + ".md")).stat().st_size // 4)
        for f in _glob.glob(str(_setup.DATABASE / "extractions/*.json"))
        if (_dp("corpus_markdown") / (json.loads(open(f).read())["doi"].replace("/", "@").lower() + ".md")).exists())
    constraints_table = integ["constraints"]
    growth_rows = growth_table()
    database_shots = json.loads((_setup.DATABASE / "config.json").read_text())["harness_params"]["n_shots"]

    values = {
        # --- the corpus ------------------------------------------------------
        "CorpusCandidates": f"{funnel['candidates found']:,}",
        "CorpusFiltered": f"{funnel['passed the filter']:,}",
        "CorpusConverted": f"{funnel['converted to chunked text']:,}",
        "DatabasePapers": f"{co['extraction']['papers processed']:,}",
        "DatabaseYielding": f"{co['extraction']['papers yielding records']:,}",
        "DatabaseEmpty": f"{co['extraction']['papers yielding none']:,}",
        "DatabaseRecords": f"{co['extraction']['records']:,}",
        "DatabaseMedianRecords": f"{co['extraction']['median records per yielding paper']:.0f}",
        "DatabaseLargestPaper": f"{co['extraction']['largest single paper']:,}",
        # --- the judge on the database ---------------------------------------
        "JudgeRecords": f"{counts['records judged']:,}",
        "JudgeAccepted": f"{counts['accepted']:,}",
        "JudgeCorrected": f"{counts['rejected, with a correction']:,}",
        "JudgeDropped": f"{counts['rejected outright']:,}",
        "JudgePassRate": f"{ve['pass rate'] * 100:.1f}",
        "JudgeCorrectedShare": f"{counts['rejected, with a correction'] / counts['records judged'] * 100:.1f}",
        "JudgeFieldFixes": f"{int(ve['fields'].sum()):,}",
        "JudgeDroppedShare": f"{counts['rejected outright'] / counts['records judged'] * 100:.1f}",
        # --- provenance ------------------------------------------------------
        "CitationsTotal": f"{pr['counts']['total']:,}",
        "CitationsResolved": f"{pr['counts'][RESOLVED_KEY]:,}",
        "CitationsTraceable": f"{pr['traceable'] * 100:.1f}",
        # --- chemistry -------------------------------------------------------
        "RouteGlycolysis": f"{int(routes.get('glycolysis', 0)):,}",
        "RouteHydrolysis": f"{int(routes.get('hydrolysis', 0)):,}",
        "RouteMethanolysis": f"{int(routes.get('methanolysis', 0)):,}",
        "DistinctCatalysts": f"{ch['distinct catalysts']:,}",
        "YieldOverHundred": f"{int(ch['out of range'].loc['yield_percent', 'above 100%']):,}",
        "IdentityPairs": f"{int(identity['pairs with both']):,}",
        "IdentityImpossible": f"{int(identity['yield above conversion']):,}",
        "ConversionCoverage": f"{ch['completeness']['conversion %'] * 100:.0f}",
        # --- the curated benchmark -------------------------------------------
        "CuratedExperiments": f"{len(curated_rows):,}",
        "CuratedPapers": f"{curated_rows.doi.nunique():,}",
        # --- the adjudication -------------------------------------------------
        "AdjRecords": f"{audit['records'].shape[0]:,}",
        "AdjJudgeFlagged": f"{int(table.loc['judge', 'flagged']):,}",
        "AdjJudgePrecision": f"{table.loc['judge', 'precision']:.2f}",
        "AdjJudgeRecall": f"{table.loc['judge', 'recall']:.2f}",
        "AdjJudgeFone": f"{table.loc['judge', 'F1']:.2f}",
        "AdjJudgeKappa": f"{table.loc['judge', 'kappa']:.2f}",
        "AdjMetricFlagged": f"{int(table.loc['metric', 'flagged']):,}",
        "AdjMetricPrecision": f"{table.loc['metric', 'precision']:.2f}",
        "AdjMetricRecall": f"{table.loc['metric', 'recall']:.2f}",
        "AdjMetricFone": f"{table.loc['metric', 'F1']:.2f}",
        "AdjMetricKappa": f"{table.loc['metric', 'kappa']:.2f}",
        "AdjPairs": f"{mcnemar['informative pairs']:,}",
        "AdjFavourJudge": f"{mcnemar['favouring the judge']:,}",
        "AdjFavourMetric": f"{mcnemar['favouring the metric']:,}",
        "AdjMcNemarP": sci(mcnemar["p"]),
        "AdjJudgeWinRate": f"{mcnemar['favouring the judge'] / mcnemar['informative pairs'] * 100:.0f}",
        "AdjAcceptedPool": f"{audit['pool']['accepted_frame']:,}",
        "AdjAcceptedAnswered": f"{audit['pool']['sampled']:,}",
        "AdjAcceptedWeight": f"{audit['pool']['weight']:.2f}",
        "AdjPriorPairs": f"{audit['prior_pairs']}",
        "LabelledRecords": f"{len(_setup.golden())}",
        "AdjAcceptedDrawn": f"{worklist.AGREEMENTS}",
        "AdjJudgeTruePositives": f"{int(table.loc['judge', 'of those wrong'])}",
        "AdjMetricTruePositives": f"{int(table.loc['metric', 'of those wrong'])}",
        # rule of three: seeing no wrong record in n of them bounds the rate at about 3/n
        "AdjMissRateBound": f"{300 / audit['pool']['sampled']:.0f}",
        # spelled out, because a LaTeX control sequence cannot contain a digit
        **{f"AdjPowerAt{WORDS[int(rate * 100)]}": f"{power:.2f}"
           for rate, power in audit["power"].items()},
        # --- prompt ablations -------------------------------------------------
        "ShotsDelta": f"{contrast['delta']:+.3f}",
        "ShotsP": f"{contrast['p']:.3f}",
        "ShotsAnovaP": f"{contrast['anova_p']:.2f}",
        "ShotsBest": f"{contrast['best']}",
        "SourceDelta": f"{src['mean'].get('citing sources', 0) - src['mean'].get('not citing', 0):+.3f}",
        "SourceCiting": f"{src['mean'].get('citing sources', float('nan')):.3f}",
        "SourceCitingSd": f"{src['std'].get('citing sources', float('nan')):.3f}",
        "SourceNot": f"{src['mean'].get('not citing', float('nan')):.3f}",
        "SourceNotSd": f"{src['std'].get('not citing', float('nan')):.3f}",
        "SourceP": f"{src.attrs.get('p', float('nan')):.3f}",
        # --- things the reviewer found contradicting themselves ---------------
        "CitationsUnresolved": f"{pr['counts']['match no chunk anywhere'] + pr['counts']['copied from a worked example']:,}",
        "CitationsUntraceable": f"{100 - pr['traceable'] * 100:.1f}",
        "CitationsCopied": f"{pr['counts']['copied from a worked example']:,}",
        "CitationsNoMatch": f"{pr['counts']['match no chunk anywhere']:,}",
        "RouteOther": f"{int(routes.get('other/unclear', 0)):,}",
        "RouteNamedTotal": f"{int(routes.drop('other/unclear', errors='ignore').sum()):,}",
        "CorrectedRecords": f"{counts['records judged'] - counts['rejected outright']:,}",
        "GrowthCuratedFone": f"{growth_rows['f1'].iloc[0]:.3f}",
        "GrowthCuratedPrecision": f"{growth_rows['precision'].iloc[0]:.3f}",
        "GrowthVouchedFone": f"{growth_rows['f1'].iloc[1]:.3f}",
        "GrowthVouchedPrecision": f"{growth_rows['precision'].iloc[1]:.3f}",
        "GrowthVouchedExperiments": f"{int(growth_rows['experiments'].iloc[1]):,}",
        "GrowthVouchedAdded": f"{int(growth_rows['added'].iloc[1]):,}",
        "BenchShots": f"{int(ex['n_shots'].iloc[0])}",
        "BenchRepeats": f"{int(ex['runs'].min())}",
        "DatabaseShots": f"{database_shots}",
        "MatrixShippedAll": f"{mx_ship['agreement']:.3f}",
        "MatrixShippedEvaluable": f"{mx_ship['agreement, evaluable']:.3f}",
        "MatrixEvaluableLow": f"{mx['agreement, evaluable'].min():.3f}",
        "MatrixEvaluableHigh": f"{mx['agreement, evaluable'].max():.3f}",
        "MatrixGapLow": f"{(mx['agreement, evaluable'] - mx['agreement']).min() * 100:.0f}",
        "MatrixGapHigh": f"{(mx['agreement, evaluable'] - mx['agreement']).max() * 100:.0f}",
        "AdjAcceptedReviewed": f"{int((audit['records'].stratum == 'both accepted it').sum())}",
        "AdjAcceptedSampled": f"{int(((audit['records'].stratum == 'both accepted it') & (audit['records'].design_stratum == 'both accepted it')).sum())}",
        "AdjAcceptedMovedIn": f"{int(((audit['records'].stratum == 'both accepted it') & (audit['records'].design_stratum != 'both accepted it')).sum())}",
        "AdjDecidedFresh": f"{decided_fresh}",
        "AdjCarriedOver": f"{audit['records'].shape[0] - decided_fresh}",
        "AdjDesignAccepted": f"{int((audit['records'].design_stratum == 'both accepted it').sum())}",
        "JudgeContextCap": "131{,}072",
        "JudgeOverContext": "0",
        "LargestJudgedTokens": f"{largest_judged:,}",
        "FunnelDroppedPolymer": f"{abs(int(funnel['dropped, no polymer named'])):,}",
        "FunnelDroppedRoute": f"{abs(int(funnel['dropped, no depolymerisation route named'])):,}",
        "FunnelDroppedOffTopic": f"{abs(int(funnel['dropped, off-topic or a review'])):,}",
        "FunnelPassRate": f"{100 * int(funnel['passed the filter']) / int(funnel['candidates found']):.1f}",
        "DatabaseCost": f"{database_meta['cost_usd']:.2f}",
        "FieldTopCount": f"{int(ve['fields'].iloc[0]):,}",
        "FieldSecondCount": f"{int(ve['fields'].iloc[1]):,}",
        "ShotsComparisons": f"{shots_comparisons}",
        "ShotsBonferroni": f"{0.05 / shots_comparisons:.3f}",
        "ShotsSmallestPairwise": f"{shots_smallest_pairwise:.2f}",
        "WithinPaperRho": f"{within_lead['within']:.2f}",
        "WithinPaperP": sci(within_lead['p']),
        # the pooled figure the within-paper one is contrasted against; the contrast is
        # the point, so both halves of it must come from the same computation
        "WithinPooledRho": f"{within_lead['pooled']:+.3f}",
        "WithinPooledN": f"{int(within_lead['pooled n']):,}",
        "GrowthAllExperiments": f"{int(growth_rows['experiments'].iloc[2]):,}",
        "GrowthAllAdded": f"{int(growth_rows['added'].iloc[2]):,}",
        "GrowthAllPrecision": f"{growth_rows['precision'].iloc[2]:.3f}",
        "GrowthAllFone": f"{growth_rows['f1'].iloc[2]:.3f}",
        "CostLuna": f"{cost_luna:.2f}",
        "CostTerra": f"{cost_terra:.2f}",
        "WithinPaperPapers": f"{int(within_lead['papers'])}",
        "WithinPaperPositive": f"{100 * within_lead['as predicted']:.0f}",
        "WithinPaperShare": f"{100 * int(within_lead['papers']) / int(co['extraction']['papers yielding records']):.0f}",
        "AdjBothFlagged": f"{int((audit['records'].design_stratum == 'both flagged it').sum())}",
        "AdjDesignDisagree": f"{int((audit['records'].design_stratum == 'graders disagree').sum())}",
        "CorpusNotObtained": f"{int(funnel['passed the filter']) - int(funnel['converted to chunked text']):,}",
        "CorpusUnextracted": f"{int(funnel['converted to chunked text']) - int(funnel['extracted so far']):,}",
        **{f"Corpus{tag}": f"{count:,}" for tag, count in obtained_by().items()},
        # --- the integrity questions a referee asks first ---------------------
        "ExemplarPool": f"{integ['contamination']['worked-example pool']}",
        "ExemplarsInBenchmark": f"{integ['contamination']['examples that are also benchmark papers']}",
        "BenchmarkInCorpus": f"{integ['contamination']['benchmark papers inside the mass corpus']}",
        "AnnotatorsShared": f"{int(integ['annotators']['records both annotators touched'])}",
        "AnnotatorsIndependent": f"{int(integ['annotators']['both decided independently'])}",
        "ConstraintRecords": f"{int(constraints_table.records.sum()):,}",
        "ConstraintFlagged": f"{int(constraints_table.flagged.sum()):,}",
        "ConstraintCaught": f"{100 * constraints_table.flagged.sum() / constraints_table.records.sum():.0f}",
        "ConstraintOverHundredCaught": f"{100 * constraints_table.loc['yield above 100%', 'judge caught']:.0f}",
        "ConstraintOverConversionCaught": f"{100 * constraints_table.loc['yield above conversion', 'judge caught']:.0f}",
        "AdjNowDisagree": f"{int((audit['records'].stratum == 'graders disagree').sum())}"
            if "stratum" in audit["records"] else "n/a",
    }
    for name, frame in sweeps.items():
        values[f"Threshold{name.capitalize()}Gap"] = (
            f"{frame['f1'].max() - frame['f1'].loc[{'accept': 0.30, 'catalyst': 0.60, 'tolerance': 0.20}[name]]:.3f}")
        values[f"Threshold{name.capitalize()}Best"] = f"{frame['f1'].idxmax():g}"
    for model in ex.index:
        key = str(model).capitalize()
        values[f"Bench{key}Fone"] = f"{ex.loc[model, 'f1']:.3f}"
        values[f"Bench{key}Sd"] = f"{ex.loc[model, 'f1 sd']:.3f}"
        values[f"Bench{key}Runs"] = f"{int(ex.loc[model, 'runs'])}"
        values[f"Bench{key}Shots"] = f"{int(ex.loc[model, 'n_shots'])}"

    runs = {
        "database": _setup.DATABASE, "database judge": _setup.DATABASE_JUDGE,
        "benchmark": _setup.EXTRACTION, "benchmark judge": _setup.JUDGE,
        "adjudication": adjudicated.REAL,
    }
    return values, runs


def write_field_table(fields) -> None:
    """The judge's field corrections as tabular rows, one label and count per row.

    Typed by hand this table summed to 610 against a text claiming 2,812, and named the catalyst
    mass 153 where the figure beside it said 628. Generated, it cannot say either.
    """
    rows = [(FIELD_LABELS.get(name, str(name)), int(count)) for name, count in fields.items()]
    # One label/count pair per row. Two pairs overflowed \columnwidth in the two-column layout,
    # and a full-width table* float doubled the overfull warnings, so the table is narrow and tall.
    body = [f"{label} & {count:,} \\\\" for label, count in rows]

    # The rows only, as a macro. \input inside a tabular lands between rows and booktabs then
    # reports "Misplaced \noalign"; and the two manuscripts use different table styles
    # (booktabs against RSC's tabular*), so a whole-tabular fragment cannot serve both.
    FIELD_TABLE.write_text("\n".join([
        "% Generated by tools/paper_numbers.py -- do not edit.",
        "\\newcommand{\\FieldTableRows}{%",
        *body, "}", ""]), encoding="utf-8")


def obtained_by() -> dict:
    """How many of the converted papers came in by each route.

    The manuscripts' funnel did not close: it listed 806 reachable under the publisher
    entitlements and 582 by other means, summing to 1,388 against 1,027 actually retrieved, and
    implied 187 out of reach where the text said 549. Counting the corpus itself instead of
    reciting candidate pools makes the column add up.
    """
    import csv
    from core.paths import data_path
    kept = {row["doi"].lower() for row in
            csv.DictReader(data_path("corpus_candidates.csv").open(encoding="utf-8"))
            if row["keep"].lower() == "true"}
    fmt = {row["doi"].lower(): row["format"] for row in
           csv.DictReader(data_path("source_format.csv").open(encoding="utf-8"))}
    converted = {path.stem.replace("@", "/").lower()
                 for path in data_path("corpus_markdown").glob("*.md")}
    tags = {"Elsevier XML": "ElsevierXml", "Europe PMC JATS": "EuropePmc", "PDF": "Pdf"}
    counts = {name: 0 for name in tags.values()}
    counts["OtherSource"] = 0
    for doi in converted & kept:
        counts[tags.get(fmt.get(doi), "OtherSource")] += 1
    return counts


def write_matrix_table() -> None:
    """The judge x extraction agreement grid, as rows.

    Typed by hand this table drifted away from the panel drawing the same numbers: it read 0.733
    where the check says 0.800, and matched neither half of itself.
    """
    from curated import matrix as matrix_check
    grid = matrix_check.compute()
    models = sorted(grid.extraction.unique())
    lines = []
    for judge in models:
        cells = []
        for column in ("agreement", "agreement, evaluable"):
            for extraction in models:
                row = grid[(grid.judge == judge) & (grid.extraction == extraction)]
                cells.append(f"{row[column].iloc[0]:.3f}" if len(row) else "---")
        lines.append(f"{judge.capitalize():6s} & " + " & ".join(cells) + " \\\\")
    MATRIX_TABLE.write_text("\n".join([
        "% Generated by tools/paper_numbers.py -- do not edit.",
        "\\newcommand{\\MatrixTableRows}{%", *lines, "}", ""]), encoding="utf-8")


def _decided_fresh() -> int:
    """Verdicts decided in this round, as opposed to carried over from the rescue review."""
    from core.paths import ARTIFACTS as _A
    base = _A / "gold" / "decisions"
    raw = {}
    for who in ("karim", "mohammad"):
        path = base / f"adjudication_{who}.json"
        if not path.exists():
            continue
        for row in json.loads(path.read_text())["decisions"]:
            raw.setdefault((row["doi"], row["extracted_index"]), {})[who] = bool(row.get("carried_over"))
    fresh = 0
    for row in json.loads((base / "adjudicated.json").read_text())["decisions"]:
        key = (row["doi"], row["extracted_index"])
        flags = [raw.get(key, {}).get(w) for w in (row.get("decided_by") or []) if w in raw.get(key, {})]
        if not (flags and all(flags)):
            fresh += 1
    return fresh


def growth_table():
    """The answer-key growth rows, from the check that prints them."""
    from human import growth
    return growth.compute()


def sci(value: float, digits: int = 0) -> str:
    mantissa, exponent = f"{value:.{digits}e}".split("e")
    return f"{mantissa}\\times10^{{{int(exponent)}}}"


def inputs() -> dict:
    """The data the runs were scored against, which moves numbers without touching a run.

    The curated table is the obvious one: growing it from 253 to 295 experiments moved every
    benchmark score and the whole shots ablation, while every run directory stayed byte-identical.
    A hash over runs alone would have declared the same artifact set for both.
    """
    from core.paths import data_path
    return {
        "curated table": data_path(_setup.CURATED),
        "corpus markdown": data_path("corpus_markdown"),
    }


def _digest_of(path: Path) -> str:
    """Content for a file; a manifest of names and sizes for a directory."""
    if path.is_dir():
        manifest = "".join(f"{f.name}:{f.stat().st_size};"
                           for f in sorted(path.glob("*.md")))
        return hashlib.sha1(manifest.encode()).hexdigest()[:16]
    if path.exists():
        return hashlib.sha1(path.read_bytes()).hexdigest()[:16]
    return "missing"


def artifact_hash(runs: dict) -> str:
    """A hash over every run the numbers came from, and every input those runs were scored on."""
    parts = [f"{name}={_digest_of(Path(path))}" for name, path in sorted(inputs().items())]
    for name, path in sorted(runs.items()):
        path = Path(path)
        marker = path / "config.json"
        if marker.exists():
            payload = json.loads(marker.read_text())
            parts.append(f"{name}={payload.get('content_hash', marker.stat().st_mtime_ns)}")
        elif path.exists():
            parts.append(f"{name}={hashlib.sha1(path.read_bytes()).hexdigest()[:16]}")
        else:
            parts.append(f"{name}=missing")
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def _define(name: str, value, derivation: str = "") -> str:
    """One \\newcommand, with what the number means beside it.

    The prose used to live in a separate document, generated by a second tool, enforced in both
    directions and re-checked for staleness on every build -- 678 lines to keep a paragraph next
    to a number. Putting it in the comment puts it where a reader of the .tex already is.
    """
    text = derivation or DERIVATION.get(name, "")
    comment = f"  % {' '.join(text.split())}" if text else ""
    return f"\\newcommand{{\\{name}}}{{{value}}}{comment}"


def render(values: dict, runs: dict) -> str:
    digest = artifact_hash(runs)
    lines = [
        "% Generated by tools/paper_numbers.py -- do not edit.",
        "% Every number the manuscripts quote is defined here, computed from the checks in one",
        "% pass, so the same quantity cannot appear twice with two values.",
        f"% artifact set {digest}, written {date.today().isoformat()}",
        "%",
    ]
    for name, path in sorted({**runs, **inputs()}.items()):
        shown = Path(path)
        lines.append(f"%   {name:16s} "
                     f"{shown.relative_to(ROOT) if ROOT in shown.parents else shown}")
    lines.append("")
    lines.append(_define("ArtifactHash", digest))
    for name, value in values.items():
        lines.append(_define(name, value))

    # The released dataset is a different population from the mass run these checks read, so its
    # numbers come from the released file itself and carry their own prefix. Emitted here rather
    # than appended afterwards, because anything appended is lost the next time this runs.
    sys.path.insert(0, str(ROOT / "checks" / "release"))
    import release_numbers
    lines += ["",
              "% --- the released dataset " + "-" * 48,
              "% Computed by checks/release/release_numbers.py from",
              "% artifacts/release/pet_homogeneous_release.csv.",
              "% These describe the RELEASE. The Database* macros describe the mass run and are",
              "% a different population; the two must not be mixed in one sentence."]
    for name, (value, _, derivation) in release_numbers.compute().items():
        lines.append(_define(name, value, derivation))
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(prog="paper_numbers")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if the file on disk differs from what the checks say now")
    args = parser.parse_args()

    values, runs = collect()
    text = render(values, runs)

    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        stale = [line for line in text.splitlines()
                 if line.startswith("\\newcommand") and line not in current]
        print(f"{len(values)} macros; {len(stale)} differ from {OUT.name}")
        for line in stale[:12]:
            print("  ", line)
        raise SystemExit(1 if stale else 0)

    OUT.write_text(text, encoding="utf-8")
    write_field_table(verdicts.compute()["fields"])
    write_matrix_table()
    print(f"{len(values)} macros -> {OUT.relative_to(ROOT)}")
    print(f"field table   -> {FIELD_TABLE.relative_to(ROOT)}")
    print(f"matrix table  -> {MATRIX_TABLE.relative_to(ROOT)}")
    print(f"artifact set {artifact_hash(runs)}")
    for name, path in sorted(runs.items()):
        print(f"  {name:16s} {path}")


if __name__ == "__main__":
    main()
