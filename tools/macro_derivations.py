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

    "IntervalHydrolysisHeavy":
        "Share of hydrolysis records charging 2 g of catalyst or more. Large, because alkaline "
        "hydrolysis consumes its base stoichiometrically; the counted-interval figure shows it "
        "directly where a smoothed density does not.",
    "IntervalGlycolysisHeavy": "The same share for glycolysis, which is small.",

    "WithinPooledMax":
        "The largest absolute pooled correlation among the four relationships chemistry "
        "predicts the sign of. Small: pooling across studies destroys all four, which is the "
        "point the within-paper figures are contrasted against.",

    "GrowthMetricBefore": "Metric-grader agreement with the chemists against the curated key.",
    "GrowthMetricAfter":
        "The same after the judge-accepted records are promoted into the key. Lower: the "
        "enlarged key is a worse reference, not a better one.",
    "GrowthMetricDelta": "The change between those two, which is negative.",
    "GrowthMetricLow": "Bootstrap 95% lower bound on that change.",
    "GrowthMetricHigh": "Upper bound. Excludes zero, so the fall is not sampling noise.",
    "GrowthMetricMoved":
        "Verdicts that move when the key grows. None of them move toward the chemists.",
    "FormatElsevierYield": "Share of Elsevier XML papers yielding at least one record.",
    "FormatEuropePmcYield": "The same for Europe PMC JATS deposits.",
    "FormatPdfYield":
        "The same for converted PDFs. Close to the other two, which is the answer to whether a "
        "PDF is read worse than a markup format.",
    "MatrixAllLow": "Lowest all-record agreement of the nine judge-extractor cells.",
    "MatrixAllHigh": "Highest.",
    "GaoOursOnPapers":
        "Records this work holds on the papers Gao et al. also describe. The denominator for "
        "our side of that comparison.",

    "WithinLongerPapers":
        "Papers with enough records to correlate reaction time against yield. The denominator "
        "of the one predicted relationship the data does not support.",
    "WithinLongerShare":
        "Share of those papers whose correlation runs the predicted way. Near half, which is "
        "what a coin would reach, and reported for that reason.",
    "WithinLongerP":
        "Wilcoxon signed-rank p for that relationship against zero. Above 0.05: longer reaction "
        "times do not give more product once each paper is compared with itself.",

    "ConstraintOverConversion":
        "Records whose yield exceeds their conversion, which is an identity rather than a "
        "correlation, so every one of them is wrong without anyone labelling it. The "
        "denominator for the share of them the judge caught.",

    "ThresholdAccept":
        "The accept threshold: a matched pair counts as a true positive below this mean record "
        "penalty. Frozen at 0.30 and read straight from checks/_setup.py.",
    "ThresholdCatalyst":
        "The catalyst gate: two catalyst names must be at least this similar (SequenceMatcher "
        "ratio) for a pair to match at all. The Methodology stated 0.80; the value used to "
        "compute every score in the manuscript is this one.",
    "ThresholdCatalystPercent": "ThresholdCatalyst as a percentage, for prose.",
    "ThresholdTolerance":
        "The numeric tolerance: a number's penalty scales with relative error and saturates at "
        "this fraction.",
    "ThresholdTolerancePercent": "ThresholdTolerance as a percentage, for prose.",

    "RouteGlycolysisShare": "Glycolysis records as a percentage of the database.",
    "RouteHydrolysisShare": "Hydrolysis records as a percentage of the database.",
    "RouteMethanolysisShare": "Methanolysis records as a percentage of the database.",
    "RouteOtherShare":
        "Records whose solvent names no route, as a percentage of the database. The share the "
        "three named routes do not account for.",
    "EmptyUnclassified":
        "Papers that yielded no records and whose titles did not say why. The residual of the "
        "three named reasons.",
    "EmptyBiological": "Papers yielding nothing because they concern enzymatic or biological "
                       "degradation, which is out of scope.",
    "EmptyOffTarget": "Papers yielding nothing because they follow another route or use PET "
                      "only as a material.",
    "EmptyReview": "Papers yielding nothing because they are reviews without protocols.",
    "MatrixRecords":
        "Benchmark records each judge-extractor pair was scored over. The denominator of the "
        "agreement figures and of the agreement pie in fig_graders.",
    "AdjJudgeAgrees":
        "How often the judge's verdict matches the chemists', over the reviewed records. Not "
        "AdjJudgeWinRate, which is its share of the records the two graders disagree on: that "
        "is a different question over a different denominator, and the abstract quoted it for "
        "this one.",
    "AdjJudgeAgreesWeighted":
        "The same, weighted by sampling stratum. Disagreements were reviewed exhaustively and "
        "mutual acceptances sub-sampled, so the reviewed set is enriched for disagreement and "
        "the raw rate understates agreement over the benchmark; this is the estimate for it.",
    "AdjMetricAgrees": "How often the heuristic's verdict matches the chemists', over the same "
                       "reviewed records. For contrast with AdjJudgeAgrees.",

    "StoichBaseRecords":
        "Records whose catalyst field names an alkali hydroxide (NaOH, KOH, LiOH, or those "
        "written out). In alkaline hydrolysis that base is a reagent consumed "
        "stoichiometrically, not a catalyst recovered at the end; it sits in the catalyst "
        "field because that is where the source papers put it. Quoted so the figure can say "
        "why hydrolysis reads tens of wt% catalyst.",
    "StoichBaseCatalysed":
        "The denominator for StoichBaseRecords: records naming any catalyst. Excludes the 802 "
        "that say none or leave the field blank, which are uncatalysed baselines rather than a "
        "catalyst choice.",
    "StoichBaseLoading":
        "Median loading of those alkali-hydroxide records as a percentage of the PET mass. "
        "Far above a catalytic loading, which is the point: it is stoichiometry.",

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
    "SelectivityCoverage": "Share of records reporting selectivity: the thinnest outcome field.",
    "RouteRatio":
        "Glycolysis records divided by hydrolysis plus methanolysis. The corpus is lopsided, "
        "which is why the grader study was built on glycolysis.",
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
    "GaoChart":
        "Gao records that are values read off a plotted curve. Our prompt reads tables and "
        "ignores figures, so this is a scope decision rather than a miss.",
    "GaoSi": "Gao records sitting in Supporting Information we do not hold.",
    "GaoRule": "Gao records from response-surface design tables our scope excludes.",
    "GaoWorstShare": "Agreement on the weakest field. Every other field is above it.",
    "GaoParityPairs":
        "Matched outcome values -- yield, conversion, selectivity -- with a number on both "
        "sides. All three are percentages, so one parity axis serves them.",
    "GaoParityAgree": "Of those, how many agree within GaoParitySlack percentage points.",
    "GaoParitySlack":
        "Percentage points of slack in that comparison. Absolute, not relative: these are all "
        "percentages, and a relative tolerance calls 1% against 3% a disagreement.",
    "GaoIdenticalConditions":
        "Matched pairs whose temperature is byte-identical on both sides. Reaction time is the "
        "same count.",
    "GaoIdenticalPairs": "Matched pairs reporting temperature at all, the denominator for that.",
    "GaoRuleOverruled":
        "Records the automatic rule called our extraction's miss that a chemist reading the "
        "paper reclassified as chart-read or out of scope. The shortfall is human-reduced.",
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
