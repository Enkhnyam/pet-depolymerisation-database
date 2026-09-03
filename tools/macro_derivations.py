"""What each macro means, for the %-comment beside its \\newcommand.

artifacts/paper_numbers.tex says what each macro *is*. This says what it *means*, and the two
travel together in one file rather than in a separate document that has to be regenerated and
checked for staleness.

Prose only. The four-part entries this replaces also named the topic, the check and the bundle:
the topic was a heading in a markdown file nobody read, and the other two repeat what every
check prints above its own output when it runs.

A macro with no entry here gets no comment. It used to fail the build until somebody wrote a
paragraph for it, which is friction on exactly the act -- adding a number to the paper -- that
this whole mechanism exists to make easy.
"""
DERIVATION = {

    "CorpusCandidates": "Scopus hits before any filter. The top of the funnel.",
    "CorpusFiltered":
        "Papers passing the title and abstract filter -- how many relevant papers exist. The "
        "denominator for every coverage claim.",
    "CorpusConverted":
        "Papers actually obtained and turned into chunked text. Below CorpusFiltered because "
        "of access, not relevance.",
    "CorpusNotObtained":
        "Filtered minus converted: papers we know exist and cannot read. Concentrated in ACS "
        "and RSC.",
    "CorpusUnextracted":
        "Converted minus extracted. One paper exhausted its rate-limit retries, so the corpus "
        "and the database differ by one and both numbers are reported.",
    "CorpusElsevierXml": "Obtained as Elsevier full-text XML.",
    "CorpusPdf": "Obtained as PDF: Wiley and Springer under entitlement, the rest open access.",
    "CorpusEuropePmc": "Obtained as Europe PMC JATS deposits.",
    "CorpusOtherSource": "Obtained by no other named route.",
    "FunnelDroppedPolymer": "Dropped: no polymer named.",
    "FunnelDroppedRoute": "Dropped: no depolymerisation route named.",
    "FunnelDroppedOffTopic": "Dropped: off-topic subject or a review.",
    "FunnelPassRate": "Share of candidates surviving the filter.",
    "DatabasePapers": "Papers the extractor processed.",
    "DatabaseYielding": "Papers that produced at least one record.",
    "DatabaseEmpty":
        "Papers that produced none. Mostly reviews and enzymatic work, i.e. papers that "
        "should yield none -- but this is also the audit's blind spot, since a missed "
        "experiment is invisible.",
    "DatabaseRecords": "Records extracted across the whole corpus.",
    "DatabaseMedianRecords": "Median records per yielding paper.",
    "DatabaseLargestPaper": "Records from the single largest paper.",
    "DatabaseCost": "USD spent on the mass extraction.",
    "DatabaseShots": "Worked examples in the prompt for the shipped run.",
    "JudgeRecords":
        "Records the judge read. Equals DatabaseRecords; quoted separately where the sentence "
        "is about judging.",
    "JudgeAccepted": "Verdict 'correct': accepted with nothing changed.",
    "JudgeCorrected":
        "Rejected with a proposed replacement value. The record survives into the corrected "
        "database with those fields rewritten.",
    "JudgeDropped":
        "Rejected outright -- the judge set drop_record, so cli/release.py deletes the row "
        "rather than repairing it. Partitioned on that flag, because that is what the "
        "released files act on.",
    "JudgePassRate": "Accepted as a share of judged. The headline quality figure.",
    "JudgeCorrectedShare": "Corrected as a share of judged.",
    "JudgeDroppedShare": "Dropped as a share of judged.",
    "JudgeFieldFixes":
        "Field-level changes proposed, larger than JudgeCorrected because one record can "
        "carry several.",
    "CorrectedRecords": "Rows in the corrected database: judged minus dropped.",
    "FieldTopCount": "Corrections to the most-corrected field (catalyst mass).",
    "FieldSecondCount": "Corrections to the second most-corrected field (solvent mass).",
    "JudgeContextCap": "The judge model's context window, in tokens.",
    "JudgeOverContext": "Papers that exceeded that window. Zero, so no verdict was truncated.",
    "LargestJudgedTokens": "Tokens in the longest paper judged, against the cap above.",
    "CitationsTotal": "Chunk citations across the database.",
    "CitationsResolved":
        "Citations pointing at a chunk that exists in the paper the record came from.",
    "CitationsTraceable": "Resolved as a share of all citations.",
    "CitationsUnresolved": "Citations resolving to nothing. Marked in the release, not dropped.",
    "CitationsUntraceable": "Unresolved as a share -- the complement of CitationsTraceable.",
    "CitationsCopied": "Unresolved because copied verbatim from a worked example in the prompt.",
    "CitationsNoMatch": "Unresolved and matching no chunk anywhere.",
    "RouteGlycolysis": "Records whose solvent implies glycolysis.",
    "RouteHydrolysis": "Records whose solvent implies hydrolysis.",
    "RouteMethanolysis": "Records whose solvent implies methanolysis.",
    "RouteOther": "Records whose solvent names no route, so no product is fixed.",
    "RouteNamedTotal": "The three named routes summed. With RouteOther it accounts for the corpus.",
    "DistinctCatalysts":
        "Distinct catalyst strings. Large and long-tailed, which is what defeats a grader "
        "comparing catalysts by spelling.",
    "ConversionCoverage":
        "Share of records reporting conversion. A ceiling on what the data can support.",
    "YieldOverHundred": "Records reporting a yield above 100%, which is impossible.",
    "IdentityPairs": "Records reporting both yield and conversion, so the identity can be tested.",
    "IdentityImpossible":
        "Of those, records with yield above conversion. An identity, not a correlation.",
    "GaoRecords": "Experiments Gao et al. curated by hand from the ionic-liquid glycolysis literature.",
    "GaoPapers": "Papers those came from, identified from Gao's short labels by hand.",
    "GaoShared": "Experiments both datasets describe, so agreement can be measured on them.",
    "GaoOursOnly": "Tabulated experiments we hold on those papers that the hand curation does not.",
    "GaoMissed": "Gao records tabulated in text the model read and did not pick up. The real extraction shortfall.",
    "GaoMissedShare": "Those as a share of Gao's set.",
    "GaoChartShare":
        "Share of Gao's set read off a plotted curve rather than a table. Our prompt instructs "
        "the model to read tables and ignore figures, so this gap is a scope decision.",
    "GaoSi": "Gao records sitting in Supporting Information we do not hold.",
    "GaoRule": "Gao records from response-surface design tables our scope excludes.",
    "GaoWorstShare": "Agreement on the weakest field. Every other field is above it.",
    "GaoReclassified": "Automatic reasons a chemist reading the paper overruled.",
    "WithinRoutePairs":
        "Route-relationship pairs whose median within-paper rho runs the way chemistry predicts. "
        "Strictly: an exactly-zero median counts for neither side.",
    "WithinRouteTotal": "Route-relationship pairs tested: four relationships in each of three routes.",
    "WithinPaperRho":
        "Median within-paper Spearman rho for temperature against yield. Positive, i.e. the "
        "expected chemistry, once each paper is compared only with itself.",
    "WithinPaperP":
        "Wilcoxon signed-rank p for those within-paper correlations against zero. Was typed "
        "into the body by hand as 7e-7 while the check had been returning it all along.",
    "WithinPaperPapers": "Papers with enough records to compute that correlation.",
    "WithinPaperPositive": "Share of those papers where the correlation runs the predicted way.",
    "WithinPaperShare": "Those papers as a share of all yielding papers.",
    "WithinPooledRho":
        "The same correlation pooled across every paper: near zero. Pooling is the wrong "
        "operation on optimised experiments, and the contrast with WithinPaperRho is the "
        "point.",
    "WithinPooledN": "Records behind the pooled figure.",
    "CuratedExperiments":
        "Experiments in the hand-curated answer key, including the entries the supervisors "
        "confirmed in the rescue round. Every metric-grader score is computed against this.",
    "CuratedPapers": "Papers the curated table covers.",
    "AdjRecords": "Records the chemists ruled on.",
    "AdjJudgeFlagged": "Records the judge called incorrect.",
    "AdjMetricFlagged": "Records the metric grader called incorrect.",
    "AdjJudgeTruePositives": "Of the judge's flags, how many a chemist agreed were wrong.",
    "AdjMetricTruePositives": "Of the metric's flags, how many a chemist agreed were wrong.",
    "AdjJudgePrecision": "Judge precision. Censused, so it carries no sampling error.",
    "AdjJudgeRecall":
        "Judge recall. Weighted, and wide, because its denominator reaches into the sampled "
        "pool.",
    "AdjJudgeFone": "Judge F1. As wide as recall.",
    "AdjJudgeKappa":
        "Judge agreement with the chemists beyond chance. Low, because most records are "
        "correct.",
    "AdjMetricPrecision": "Metric precision.",
    "AdjMetricRecall": "Metric recall.",
    "AdjMetricFone": "Metric F1.",
    "AdjMetricKappa": "Metric agreement beyond chance.",
    "AdjPairs":
        "Discordant pairs: records where exactly one grader matched the chemists. The only "
        "records that say which grader is better.",
    "AdjFavourJudge": "Discordant pairs won by the judge.",
    "AdjFavourMetric": "Discordant pairs won by the metric.",
    "AdjMcNemarP":
        "McNemar exact p on those pairs. Every pair is censused, so this carries no sampling "
        "error.",
    "AdjJudgeWinRate": "Judge wins as a share of discordant pairs.",
    "AdjPriorPairs":
        "Discordant pairs the earlier random round produced. Too few for any outcome to reach "
        "significance -- the reason this round censused disagreements instead.",
    "LabelledRecords": "Records in that earlier round.",
    "AdjPowerAtSixty": "Power to detect a judge right 60% of the time, at the pairs returned.",
    "AdjPowerAtSixtyFive": "Power at 65%.",
    "AdjPowerAtSeventy": "Power at 70%.",
    "AdjPowerAtSeventyFive": "Power at 75%.",
    "AdjPowerAtEighty": "Power at 80%.",
    "AdjAcceptedDrawn": "Records drawn from the both-accepted pool for the page.",
    "AdjAcceptedAnswered": "Of those, how many came back answered. The divisor for the weight.",
    "AdjAcceptedPool": "The pool those were drawn from.",
    "AdjAcceptedWeight": "What each answered record stands for: pool over answered.",
    "AdjMissRateBound":
        "Rule of three. No wrong record among the answered ones bounds the hidden rate at "
        "roughly this, which is why metric recall reads 1.00 with a wide lower bound.",
    "AdjDesignDisagree": "Records the page censused as grader disagreements.",
    "AdjBothFlagged": "Records the page censused because both graders flagged them.",
    "AdjDesignAccepted": "Records the page sampled from the both-accepted cell.",
    "AdjAcceptedReviewed": "Records in the both-accepted cell under today's verdicts.",
    "AdjAcceptedSampled": "In that cell both by design and today.",
    "AdjAcceptedMovedIn":
        "Censused on the page but in the accepted cell today, because the solvent-alias fix "
        "landed afterwards. They keep weight 1: they were never sampled.",
    "AdjNowDisagree": "Records the graders still disagree on under today's verdicts.",
    "AdjDecidedFresh": "Records a chemist actively decided.",
    "AdjCarriedOver": "Records carried in pre-filled from the rescue round and left alone.",
    "ExemplarPool": "Papers the prompt's worked examples are drawn from.",
    "ExemplarsInBenchmark": "Of those, how many are also benchmark papers. Leakage if not zero.",
    "BenchmarkInCorpus": "Benchmark papers that also sit inside the mass corpus.",
    "AnnotatorsShared": "Records both chemists touched.",
    "AnnotatorsIndependent":
        "Of those, how many both actively decided rather than leaving a pre-fill. Zero here, "
        "so this round supports no inter-annotator agreement figure and none should be "
        "quoted.",
    "ConstraintRecords": "Records wrong on arithmetic alone.",
    "ConstraintFlagged": "Of those, how many the judge also flagged.",
    "ConstraintCaught":
        "Flagged as a share -- the judge's hit rate on records that are provably wrong.",
    "ConstraintOverHundredCaught": "Hit rate on yields above 100%.",
    "ConstraintOverConversionCaught": "Hit rate on yields above conversion.",
    "MatrixShippedAll": "Judge-metric agreement for the shipped pair, over every record.",
    "MatrixShippedEvaluable": "The same, over records the metric could evaluate.",
    "MatrixEvaluableLow": "Lowest evaluable-record agreement of the nine cells.",
    "MatrixEvaluableHigh": "Highest.",
    "MatrixGapLow": "Smallest gap between all-record and evaluable-record agreement.",
    "MatrixGapHigh":
        "Largest. The gap exists because the metric marks surplus records wrong without "
        "looking at them, not because of chemistry.",
    "BenchLunaFone": "Luna F1 on the curated papers, averaged over repeats.",
    "BenchLunaSd": "Its spread across repeats -- wider than some gaps between models.",
    "BenchLunaRuns": "Repeats behind it.",
    "BenchLunaShots": "Worked examples used.",
    "BenchOssFone": "OSS F1.",
    "BenchOssSd": "OSS spread.",
    "BenchOssRuns": "OSS repeats.",
    "BenchOssShots": "OSS worked examples.",
    "BenchTerraFone": "Terra F1.",
    "BenchTerraSd": "Terra spread.",
    "BenchTerraRuns": "Terra repeats.",
    "BenchTerraShots": "Terra worked examples.",
    "BenchShots": "Worked examples the benchmark was scored at.",
    "BenchRepeats": "Repeats per arm.",
    "CostLuna": "USD to extract the curated papers with Luna.",
    "CostTerra": "The same with Terra, which scores lower and costs more.",
    "ShotsDelta": "F1 gain from one worked example over none.",
    "ShotsP": "p for that gain.",
    "ShotsAnovaP": "One-way ANOVA among the arms that have examples: nothing separates them.",
    "ShotsBest": "Arm with the highest mean. One, which is why the database ships at one.",
    "ShotsComparisons": "Pairwise comparisons available among the arms.",
    "ShotsBonferroni": "Bonferroni-corrected alpha for that many comparisons.",
    "ShotsSmallestPairwise": "Smallest pairwise p among them, against that alpha.",
    "SourceDelta": "F1 gain from requiring source citations.",
    "SourceCiting": "F1 with citations required.",
    "SourceCitingSd": "Its spread.",
    "SourceNot": "F1 without.",
    "SourceNotSd": "Its spread.",
    "SourceP": "p for the difference. Short of significance, reported as such.",
    "ThresholdAcceptGap":
        "F1 left on the table by the accept threshold. Reported and not taken: moving it now, "
        "to maximise a score on the papers the score is computed from, is the tuning we claim "
        "not to do.",
    "ThresholdAcceptBest": "Where the accept threshold would have peaked.",
    "ThresholdCatalystGap": "The same for the catalyst gate.",
    "ThresholdCatalystBest": "Where it would have peaked.",
    "ThresholdToleranceGap": "The same for the numeric tolerance.",
    "ThresholdToleranceBest": "Where it would have peaked.",
    "GrowthCuratedPrecision": "Precision against the curated key as it stands.",
    "GrowthCuratedFone": "F1 against the same.",
    "GrowthVouchedExperiments": "Key size after promoting judge-accepted records into it.",
    "GrowthVouchedAdded": "How many that added.",
    "GrowthVouchedPrecision": "Precision against the grown key.",
    "GrowthVouchedFone":
        "F1 against it. Higher without a single extracted record changing, which is why a key "
        "grown from the extraction's own output overstates quality.",
    "GrowthAllExperiments": "Key size after promoting every unmatched record.",
    "GrowthAllAdded": "How many that added.",
    "GrowthAllPrecision": "Precision against that key.",
    "GrowthAllFone": "F1 against it.",
    "ArtifactHash":
        "Hash over the config content-hashes of every run behind these numbers. Change a run "
        "and this changes, so the manuscript declares which artifact set it describes.",
}
