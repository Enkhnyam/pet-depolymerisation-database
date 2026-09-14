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
sys.path.insert(0, str(ROOT / "checks"))
sys.path.insert(0, str(ROOT / "tools"))

from core.paths import ARTIFACTS
from core.schema import OTHER_ROUTE, ROUTES

# The five condition fields, for the Gao completeness range. The outcome fields are reported
# inconsistently by the source papers themselves, so a range over all ten would describe the
# literature rather than the extraction.
CONDITION_FIELDS = ["temperature_c", "reaction_time_min", "catalyst_amount_g",
                    "PET_amount_g", "solvent_amount_g"]
from macro_derivations import DERIVATION
import _setup
import cost
from curated import extractions, gao_overlap, matrix, shots, source_tracking, thresholds
from database import chemistry, corpus, formats, provenance, verdicts, withinpaper
from human import adjudicated, corrections, growth, integrity, worklist

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

# How the manuscript names each model. The matrix table used to spell these out beside nine
# hand-typed cells; one of them, \textbf{0.935}, sat two cells from \MatrixEvaluableHigh{}
# reading the same grid.
MODEL_LABELS = {"luna": "GPT-5.6 Luna", "oss": "GPT-OSS-120B", "terra": "GPT-5.6 Terra"}

# \AdjPowerAt70 is not a legal control sequence, so the rates are spelled out.
WORDS = {60: "Sixty", 65: "SixtyFive", 70: "Seventy", 75: "SeventyFive", 80: "Eighty"}

# The macro names are deliberately verbose: \DatabaseRecords is unmistakable in a manuscript in a
# way that \NR is not, and the point of this file is that a reader of the .tex can see where a
# number came from.
def collect() -> tuple[dict, dict]:
    """Every quoted number, read off the checks. Nothing here computes.

    It used to. This function carried twelve imports in its body -- `from curated import matrix
    as _matrix`, `import cost as _cost`, `from scipy.stats import ttest_ind as _tt` -- and its
    own pairwise t-tests, its own cost arithmetic, its own glob over every extraction file
    (parsed twice per iteration), its own re-read of corpus_candidates.csv. Every one of those
    was a second implementation of a question a check already owned, so the two could and did
    drift: the shots pairwise count here was ten while shots.py printed fifteen.
    """
    co, ch, ve, pr = corpus.compute(), chemistry.compute(), verdicts.compute(), provenance.compute()
    base = ch["stoichiometric base"]
    empty = co["empty papers"]
    # Share of each route's records charging 2 g of catalyst or more, the interval the counted
    # figure makes the alkaline-hydrolysis story visible in.
    heavy = (ch["records"].dropna(subset=["catalyst_amount_g"])
             .groupby("route").catalyst_amount_g.apply(lambda s: s.ge(2).mean()))
    ex = extractions.arms()
    sh = shots.compute()
    contrast = shots.contrast(sh)
    pairs_frame = shots.pairwise(sh)
    src = source_tracking.compute()
    sweeps = thresholds.compute()
    audit = adjudicated.compute(adjudicated.REAL)
    _corr = corrections.compute()
    table, mcnemar = audit["table"], audit["mcnemar"]
    counts, funnel = ve["counts"], co["funnel"]
    routes = ch["by route"]["records"]
    identity = ch["identity"]
    curated_rows = _setup.curated()
    integ = integrity.compute()
    mx = matrix.compute()
    mx_ship = mx[(mx.judge == "oss") & (mx.extraction == "luna")].iloc[0]
    tracking = growth.tracking()
    reach = formats.compute()["reach"]
    route_trends_table = withinpaper.compute()["table"]
    within_lead = route_trends_table.loc["hotter gives more"]
    growth_rows = growth.compute()
    gao = gao_overlap.compute()
    by_paper = gao["per paper"]
    paper_gap = by_paper["hand-curated"] - by_paper["this work"]
    route_trends = withinpaper.by_route()
    constraints_table = integ["constraints"]
    database_meta = json.loads((_setup.DATABASE / "run_meta.json").read_text())
    database_shots = json.loads(
        (_setup.DATABASE / "config.json").read_text())["harness_params"]["n_shots"]
    # The cost-against-score plane the SI's choices figure draws, and the arm on it that ships.
    _configs = extractions.configurations()
    _shipped = _configs[(_configs.model == "luna")
                        & (_configs.n_shots == int(database_shots))].iloc[0]

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
        # Why the papers that produced nothing produced nothing. The funnel table's own total
        # did not include the fourth way full text was obtained, and these four reasons were
        # typed into the body.
        "EmptyUnclassified": f"{int(empty['unclassified']):,}",
        "EmptyBiological": f"{int(empty['enzymatic or biological']):,}",
        "EmptyOffTarget": f"{int(empty['other route or material']):,}",
        "EmptyReview": f"{int(empty['review article']):,}",
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
        # The interval figure's headline: the stoichiometric-base story as a share, which is
        # what a counted interval shows and a smoothed density smooths away.
        "IntervalHydrolysisHeavy": f"{100 * heavy['hydrolysis']:.0f}",
        "IntervalGlycolysisHeavy": f"{100 * heavy['glycolysis']:.0f}",
        "StoichBaseRecords": f"{base['records']:,}",
        "StoichBaseCatalysed": f"{base['of records naming a catalyst']:,}",
        "StoichBaseLoading": f"{base['median wt% of PET']:.0f}",
        "ConversionCoverage": f"{ch['completeness']['conversion %'] * 100:.0f}",
        "SelectivityCoverage": f"{ch['completeness']['selectivity %'] * 100:.0f}",
        "RouteRatio": f"{routes['glycolysis'] / routes.reindex(ROUTES[1:]).sum():.1f}",
        # Route shares. The manuscript quoted 48/25/10 as literals in both a caption and the
        # body; they are right, and they were three numbers that would not have moved when the
        # route rules did.
        "RouteGlycolysisShare": f"{100 * routes['glycolysis'] / routes.sum():.0f}",
        "RouteHydrolysisShare": f"{100 * routes['hydrolysis'] / routes.sum():.0f}",
        "RouteMethanolysisShare": f"{100 * routes['methanolysis'] / routes.sum():.0f}",
        "RouteOtherShare": f"{100 * routes[OTHER_ROUTE] / routes.sum():.0f}",
        # --- the curated benchmark -------------------------------------------
        "CuratedExperiments": f"{len(curated_rows):,}",
        "CuratedPapers": f"{curated_rows.doi.nunique():,}",
        # --- what a proposed correction is worth, by what it asks you to do ---
        "CorrSampled": f"{_corr.attrs['sampled']}",
        "CorrAccepted": f"{_corr.attrs['accepted']}",
        "CorrAcceptedDefensible": f"{_corr.attrs['accepted but defensible']}",
        "CorrCaught": f"{int(_corr[corrections.CAUGHT].sum())}",
        "CorrBoth": f"{int(_corr[corrections.BOTH].sum())}",
        "CorrRejected": f"{int(_corr[corrections.REJECTED].sum())}",
        "CorrBestShare": f"{100 * _corr['caught share'].iloc[0]:.0f}",
        "CorrWorstShare": f"{100 * _corr['caught share'].iloc[-1]:.0f}",
        "CorrRenameCases": f"{int(_corr.loc['substance', 'cases'])}",
        "CorrRenameCaught": f"{int(_corr.loc['substance', corrections.CAUGHT])}",
        "CorrRenameBoth": f"{int(_corr.loc['substance', corrections.BOTH])}",
        "CorrNumberCases": f"{int(_corr.loc['number', 'cases'])}",
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
        # AdjJudgeWinRate is the judge's share of the records the two graders disagree on. It
        # is NOT how often the judge agrees with the chemists, and the abstract quoted it as if
        # it were. AdjJudgeAgrees is that second quantity, over the reviewed records; the
        # weighted variant is the estimate over the benchmark the reviewed set was drawn from.
        "AdjJudgeWinRate": f"{mcnemar['favouring the judge'] / mcnemar['informative pairs'] * 100:.0f}",
        "AdjJudgeAgrees": f"{audit['agreement']['judge']['raw'] * 100:.0f}",
        "AdjJudgeAgreesWeighted": f"{audit['agreement']['judge']['weighted'] * 100:.0f}",
        "AdjMetricAgrees": f"{audit['agreement']['metric']['raw'] * 100:.0f}",
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
        "MatrixRecords": f"{int(mx_ship['records']):,}",
        "MatrixShippedAll": f"{mx_ship['agreement']:.3f}",
        "MatrixShippedEvaluable": f"{mx_ship['agreement, evaluable']:.3f}",
        "MatrixEvaluableLow": f"{mx['agreement, evaluable'].min():.3f}",
        "MatrixEvaluableHigh": f"{mx['agreement, evaluable'].max():.3f}",
        "MatrixGapLow": f"{(mx['agreement, evaluable'] - mx['agreement']).min() * 100:.0f}",
        "MatrixGapHigh": f"{(mx['agreement, evaluable'] - mx['agreement']).max() * 100:.0f}",
        "AdjAcceptedReviewed": f"{int((audit['records'].stratum == 'both accepted it').sum())}",
        "AdjAcceptedSampled": f"{int(((audit['records'].stratum == 'both accepted it') & (audit['records'].design_stratum == 'both accepted it')).sum())}",
        "AdjAcceptedMovedIn": f"{int(((audit['records'].stratum == 'both accepted it') & (audit['records'].design_stratum != 'both accepted it')).sum())}",
        "AdjDecidedFresh": f"{audit['decided fresh']}",
        "AdjCarriedOver": f"{audit['records'].shape[0] - audit['decided fresh']}",
        "AdjDesignAccepted": f"{int((audit['records'].design_stratum == 'both accepted it').sum())}",
        # the window is a property of the model, so it comes from _setup where the other
        # measurement constants live; the count over it is measured, not asserted
        "JudgeContextCap": f"{_setup.JUDGE_CONTEXT:,}".replace(",", "{,}"),
        "JudgeOverContext": f"{co['papers over the judge\'s context window']}",
        "LargestJudgedTokens": f"{co['largest judged tokens']:,}",
        "FunnelDroppedPolymer": f"{abs(int(funnel['dropped, no polymer named'])):,}",
        "FunnelDroppedRoute": f"{abs(int(funnel['dropped, no depolymerisation route named'])):,}",
        "FunnelDroppedOffTopic": f"{abs(int(funnel['dropped, off-topic or a review'])):,}",
        "FunnelPassRate": f"{100 * int(funnel['passed the filter']) / int(funnel['candidates found']):.1f}",
        "DatabaseCost": f"{database_meta['cost_usd']:.2f}",
        "FieldTopCount": f"{int(ve['fields'].iloc[0]):,}",
        "FieldSecondCount": f"{int(ve['fields'].iloc[1]):,}",
        "ShotsComparisons": f"{len(pairs_frame)}",
        "ShotsBonferroni": f"{0.05 / len(pairs_frame):.3f}",
        "ShotsSmallestPairwise": f"{pairs_frame.p.min():.2f}",
        # --- the comparison against hand curation, and the test that outlives it -----------
        "GaoRecords": f"{sum(gao['split']):,}",
        "GaoPapers": f"{gao['counts']['Gao papers']}",
        "GaoShared": f"{gao['counts']['shared records']}",
        "GaoOursOnly": f"{gao['counts']['ours alone']}",
        "GaoMissed": f"{gao['split']['missed']}",
        "GaoMissedShare": f"{gao['true miss share'] * 100:.0f}",
        "GaoChartShare": f"{gao['chart share'] * 100:.0f}",
        "GaoChart": f"{gao['split']['chart']}",
        "GaoSi": f"{gao['split']['si']}",
        "GaoRule": f"{gao['split']['rule']}",
        "GaoWorstShare": f"{gao['agreement'].share.min() * 100:.0f}",
        "GaoParityPairs": f"{len(gao['parity'])}",
        "GaoParityAgree": f"{int(gao['parity'].agrees.sum())}",
        "GaoParitySlack": f"{gao_overlap.PARITY_SLACK:.0f}",
        "GaoIdenticalConditions": f"{int(gao['identical'].loc['temperature_c', 'identical'])}",
        "GaoIdenticalPairs": f"{int(gao['identical'].loc['temperature_c', 'pairs'])}",
        "GaoRuleOverruled": f"{gao['reclassified from missed']}",
        "GaoReclassified": f"{gao['reclassified']}",
        "WithinRoutePairs": f"{_route_pairs(route_trends)}",
        "WithinRouteTotal": f"{len(withinpaper.PAIRS) * len(ROUTES)}",
        "WithinPaperRho": f"{within_lead['within']:.2f}",
        "WithinPaperP": sci(within_lead['p']),
        # The relationship that does not hold. fig_trends shows all four and says so, which
        # means the caption needs the failing one's numbers as macros like any other.
        # The bound the caption states on how close every pooled coefficient sits to zero.
        # Typed as "0.06", which is both a rounding of the real 0.053 and the same digits as
        # WithinLongerP, a different quantity entirely.
        "WithinPooledMax": f"{route_trends_table['pooled'].abs().max():.3f}",
        "WithinLongerPapers": f"{int(route_trends_table.loc['longer gives more', 'papers'])}",
        "WithinLongerShare":
            f"{100 * route_trends_table.loc['longer gives more', 'as predicted']:.0f}",
        "WithinLongerP": f"{route_trends_table.loc['longer gives more', 'p']:.2f}",
        # the pooled figure the within-paper one is contrasted against; the contrast is
        # the point, so both halves of it must come from the same computation
        "WithinPooledRho": f"{within_lead['pooled']:+.3f}",
        "WithinPooledN": f"{int(within_lead['pooled n']):,}",
        # What growing the key does to the *grader*, not just to the score. The SI quotes the
        # agreement before and after, the change and its bootstrap interval; they were typed in.
        "GrowthMetricBefore": f"{tracking['agreement before'].iloc[0]:.2f}",
        "GrowthMetricAfter": f"{tracking['agreement after'].iloc[0]:.2f}",
        "GrowthMetricDelta":
            f"{tracking['agreement after'].iloc[0] - tracking['agreement before'].iloc[0]:+.2f}",
        "GrowthMetricLow": f"{tracking['95% low'].iloc[0]:+.2f}",
        "GrowthMetricHigh": f"{tracking['95% high'].iloc[0]:+.2f}",
        "GrowthMetricMoved": f"{int(tracking['labels changed'].iloc[0])}",
        # Yield rate by the format a paper arrived in: the SI's answer to whether the reader
        # should worry that a PDF is read worse than an XML.
        "FormatElsevierYield": f"{reach.loc['Elsevier XML', '% yielding']:.0f}",
        "FormatEuropePmcYield": f"{reach.loc['Europe PMC JATS', '% yielding']:.0f}",
        "FormatPdfYield": f"{reach.loc['PDF', '% yielding']:.0f}",
        # The all-records half of the agreement matrix, which the SI now reports beside the
        # evaluable half so a reader can see how much of the headline is the restriction.
        "MatrixAllLow": f"{mx['agreement'].min():.3f}",
        "MatrixAllHigh": f"{mx['agreement'].max():.3f}",
        "GaoOursOnPapers": f"{gao['counts']['records we hold on those papers']:,}",
        # How much of a record each side fills in. The SI's third comparison, beside size and
        # agreement, and the one that says where hand curation is still richer.
        # The two middling reasons in the record accounting, which the caption now names.
        # The per-paper extremes the SI caption names. The size difference is concentrated in
        # two papers and runs both ways, which is the panel's whole point, so the counts that
        # make it are macros like any other.
        "GaoPapersTheyLead": f"{int((paper_gap > 0).sum())}",
        "GaoPapersWeLead": f"{int((paper_gap < 0).sum())}",
        "GaoTopGapTheirs": f"{int(by_paper.loc[paper_gap.idxmax(), 'hand-curated'])}",
        "GaoTopGapOurs": f"{int(by_paper.loc[paper_gap.idxmax(), 'this work'])}",
        "GaoOursLeadTheirs": f"{int(by_paper.loc[paper_gap.idxmin(), 'hand-curated'])}",
        "GaoOursLeadOurs": f"{int(by_paper.loc[paper_gap.idxmin(), 'this work'])}",
        # What a disagreement between the two datasets actually looks like, which the
        # agreement table cannot say: how many of the shared numeric values are identical, and
        # how far apart the rest are.
        "GaoExtraRecords": f"{gao['extra records'].attrs['extra']:,}",
        "GaoExtraPapers": f"{gao['extra records'].attrs['extra papers']}",
        "GaoExtraCatalystGap":
            f"{-100 * gao['extra records'].loc['catalyst_amount_g', 'gap']:.0f}",
        "GaoExtraSolventGap":
            f"{-100 * gao['extra records'].loc['solvent_amount_g', 'gap']:.0f}",
        # How the surplus-completeness panel splits, counted rather than eyeballed. The caption
        # used to say "nine of the ten distances are short" and then name two exceptions, which
        # is eleven fields out of ten; and "three run the wrong way for the suspicion" counted
        # the labelled gaps rather than the positive ones, of which there are four.
        "GaoExtraFields": f"{len(gao['extra records'])}",
        # Whether the surplus is fragments is a question about records, not about fields, so
        # these come from the per-record profile rather than from the per-field one.
        "GaoSharedMean": f"{gao['fields per record'].attrs['shared mean']:.1f}",
        "GaoSurplusMean": f"{gao['fields per record'].attrs['ours only mean']:.1f}",
        "GaoSharedThin": f"{gao['fields per record'].attrs['shared thin']}",
        "GaoSurplusThin": f"{gao['fields per record'].attrs['ours only thin']}",
        "GaoThinFields": f"{gao_overlap.THIN - 1}",
        "GaoValuesCompared": f"{len(gao['disagreements']):,}",
        "GaoValuesSame": f"{int(gao['disagreements'].identical.sum()):,}",
        "GaoValuesDiffer": f"{int((~gao['disagreements'].identical).sum()):,}",
        # The score at which the best model's worst run meets the runner-up's best, which is
        # what the model panel turns on.
        "BenchOverlapScore": f"{_bench_overlap(extractions.runs(), extractions.compute()):.3f}",
        "GaoSI": f"{int(gao['split']['si'])}",
        "GaoRule": f"{int(gao['split']['rule'])}",
        "GaoFillLow": f"{100 * gao['completeness']['this work'].loc[CONDITION_FIELDS].min():.0f}",
        "GaoFillHigh": f"{100 * gao['completeness']['this work'].loc[CONDITION_FIELDS].max():.0f}",
        "GaoSelectivityGap":
            f"{100 * (gao['completeness'].loc['selectivity_percent', 'hand-curated']
                      - gao['completeness'].loc['selectivity_percent', 'this work']):.0f}",
        "GrowthAllExperiments": f"{int(growth_rows['experiments'].iloc[2]):,}",
        "GrowthAllAdded": f"{int(growth_rows['added'].iloc[2]):,}",
        "GrowthAllPrecision": f"{growth_rows['precision'].iloc[2]:.3f}",
        "GrowthAllFone": f"{growth_rows['f1'].iloc[2]:.3f}",
        "CostLuna": f"{cost.arm_cost('luna', ex.loc['luna', 'n_shots']):.2f}",
        "CostTerra": f"{cost.arm_cost('terra', ex.loc['terra', 'n_shots']):.2f}",
        # The cost-against-score plane, and the one line on it a reader should decide from: how
        # wide a repeat is, and how many arms that width fails to separate from the shipped one.
        "ChoiceArms": f"{len(_configs)}",
        "ChoiceShippedSd": f"{_shipped.sd:.3f}",
        "ChoiceWithinSpread":
            f"{int(((_configs.f1 >= _shipped.f1 - _shipped.sd) & (_configs.f1 < _shipped.f1)).sum())}",
        "ChoiceBeaten": f"{int((~_configs['on frontier']).sum())}",
        "WithinPaperPapers": f"{int(within_lead['papers'])}",
        "WithinPaperPositive": f"{100 * within_lead['as predicted']:.0f}",
        "WithinPaperShare": f"{100 * int(within_lead['papers']) / int(co['extraction']['papers yielding records']):.0f}",
        "AdjBothFlagged": f"{int((audit['records'].design_stratum == 'both flagged it').sum())}",
        "AdjDesignDisagree": f"{int((audit['records'].design_stratum == 'graders disagree').sum())}",
        "CorpusNotObtained": f"{int(funnel['passed the filter']) - int(funnel['converted to chunked text']):,}",
        "CorpusUnextracted": f"{int(funnel['converted to chunked text']) - int(funnel['extracted so far']):,}",
        **{f"Corpus{tag}": f"{count:,}" for tag, count in co["obtained by"].items()},
        # How the corpus was licensed to us, which the format counts do not say: most of the PDF
        # route is Wiley and Springer subscription content under the same entitlement that
        # supplies Elsevier's XML, not open access.
        "CorpusEntitlement": f"{co['licensed by']['under a mining entitlement']:,}",
        "CorpusOpenAccess": f"{co['licensed by']['open access']:,}",
        "CorpusWileyEntitled": f"{co['entitlement, by publisher']['Wiley']:,}",
        "CorpusSpringerEntitled": f"{co['entitlement, by publisher']['Springer']:,}",
        # --- the integrity questions a referee asks first ---------------------
        "ExemplarPool": f"{integ['contamination']['worked-example pool']}",
        "ExemplarsInBenchmark": f"{integ['contamination']['examples that are also benchmark papers']}",
        "BenchmarkInCorpus": f"{integ['contamination']['benchmark papers inside the mass corpus']}",
        "AnnotatorsShared": f"{int(integ['annotators']['records both annotators touched'])}",
        "AnnotatorsIndependent": f"{int(integ['annotators']['both decided independently'])}",
        "ConstraintRecords": f"{int(constraints_table.records.sum()):,}",
        "ConstraintFlagged": f"{int(constraints_table.flagged.sum()):,}",
        "ConstraintCaught": f"{100 * constraints_table.flagged.sum() / constraints_table.records.sum():.0f}",
        "ConstraintOverConversion": f"{int(constraints_table.loc['yield above conversion', 'records']):,}",
        "ConstraintOverHundredCaught": f"{100 * constraints_table.loc['yield above 100%', 'judge caught']:.0f}",
        "ConstraintOverConversionCaught": f"{100 * constraints_table.loc['yield above conversion', 'judge caught']:.0f}",
        "AdjNowDisagree": f"{int((audit['records'].stratum == 'graders disagree').sum())}"
            if "stratum" in audit["records"] else "n/a",
        # The three frozen settings every score in the manuscript is computed with. They had no
        # macros, so the Methodology typed them out -- and stated the catalyst gate as 0.80
        # where checks/_setup.py has held 0.60 throughout, which is the value that produced
        # every F1 in the paper.
        "ThresholdAccept": f"{_setup.ACCEPT:.2f}",
        "ThresholdCatalyst": f"{_setup.CATALYST:.2f}",
        "ThresholdCatalystPercent": f"{_setup.CATALYST * 100:.0f}",
        "ThresholdTolerance": f"{_setup.TOLERANCE:.2f}",
        "ThresholdTolerancePercent": f"{_setup.TOLERANCE * 100:.0f}",
    }
    # the settings in use, not a second copy of them: this dict was written out here as
    # {'accept': 0.30, 'catalyst': 0.60, 'tolerance': 0.20}
    FROZEN = {"accept": _setup.ACCEPT, "catalyst": _setup.CATALYST,
              "tolerance": _setup.TOLERANCE}
    for name, frame in sweeps.items():
        values[f"Threshold{name.capitalize()}Gap"] = (
            f"{frame['f1'].max() - frame['f1'].loc[FROZEN[name]]:.3f}")
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


def _bench_overlap(runs, arms) -> float:
    """Where the top model's worst run meets the runner-up's best, at the shipped setting.

    The extractor comparison rests on this: a mean says luna beats terra by 0.024, and the runs
    say luna's lowest and terra's highest are the same number. Computed rather than read off a
    panel, so the caption cannot claim a coincidence the data stops supporting.

    Both frames arrive as arguments rather than being fetched here, so the call site names the
    check they come from: tools/provenance.py attributes a macro by reading the expression that
    produces it, and a helper that fetches its own data leaves the macro traceable to nothing.
    """
    runs = runs[runs.n_shots == int(arms["n_shots"].iloc[0])]
    means = runs.groupby("model").f1.mean().sort_values(ascending=False)
    top, second = means.index[0], means.index[1]
    return round(min(runs[runs.model == top].f1.min(),
                     runs[runs.model == second].f1.max()), 3)


def _route_pairs(routes: dict) -> int:
    """Route-relationship pairs whose median within-paper rho runs the way chemistry predicts.

    Strictly: a median of exactly zero is on neither side. Reaction time against temperature in
    hydrolysis is exactly zero, and an == comparison counted it as agreeing -- which would have
    put "12 of 12" in the manuscript.
    """
    agreeing = 0
    for route, found in routes.items():
        for name, row in found["table"].iterrows():
            agreeing += row["within"] > 0 if row["expected"] == "+" else row["within"] < 0
    return int(agreeing)


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
    # The manuscript's table shows the evaluable half only, three rows of three, with the best
    # cell in bold. Emitted rather than typed, and the bold follows the maximum rather than
    # whichever cell was highest the day someone typed it.
    grid_eval = grid.pivot(index="judge", columns="extraction", values="agreement, evaluable")
    best = grid_eval.values.max()
    evaluable = []
    for judge in models:
        cells = [(f"\\textbf{{{grid_eval.loc[judge, e]:.3f}}}"
                  if grid_eval.loc[judge, e] == best else f"{grid_eval.loc[judge, e]:.3f}")
                 for e in models]
        evaluable.append(f"{MODEL_LABELS.get(judge, judge):14s} & " + " & ".join(cells) + " \\\\")

    MATRIX_TABLE.write_text("\n".join([
        "% Generated by tools/paper_numbers.py -- do not edit.",
        "\\newcommand{\\MatrixTableRows}{%", *lines, "}",
        "\\newcommand{\\MatrixEvaluableRows}{%", *evaluable, "}", ""]), encoding="utf-8")


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
