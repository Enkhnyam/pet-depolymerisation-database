"""What every manuscript macro means, where its number comes from, and why it is in the paper.

The macro file itself is a wall of \\newcommand lines: correct, but unreadable. This is the other
half -- one entry per macro saying which check computed it, which bundle that check read, and what
the number is doing in the argument. tools/macro_reference.py turns it into a document.

Kept apart from paper_numbers.py on purpose. That file's job is to compute; adding a paragraph of
prose beside each expression would bury the arithmetic. The connection between the two is enforced
rather than trusted: the reference generator fails if a macro is defined with no entry here, or an
entry here names a macro nobody defines. A new number cannot reach the paper undocumented.

Each entry is (topic, computed by, reads, meaning).
"""

# The bundles, spelled the way the checks name them, so a reader can find the directory.
MASS = "mass_luna_1shot + mass_oss_1shot"
BENCH = "extract_luna_n4_r1 + judge_oss_on_luna"
CURATED = "curated_table_final.json"
ADJ = "gold/decisions/adjudicated.json"
FUNNEL = "the Scopus search log"
RELEASE = "release/pet_homogeneous_release.csv"

CATALOGUE = {
 # --- the corpus: how many papers there are, and how many we could read -----------------
 "CorpusCandidates": ("Corpus", "database/corpus.py", FUNNEL,
   "Scopus hits before any filter. The top of the funnel."),
 "CorpusFiltered": ("Corpus", "database/corpus.py", FUNNEL,
   "Papers passing the title and abstract filter -- how many relevant papers exist. The "
   "denominator for every coverage claim."),
 "CorpusConverted": ("Corpus", "database/corpus.py", FUNNEL,
   "Papers actually obtained and turned into chunked text. Below CorpusFiltered because of "
   "access, not relevance."),
 "CorpusNotObtained": ("Corpus", "database/corpus.py", FUNNEL,
   "Filtered minus converted: papers we know exist and cannot read. Concentrated in ACS and RSC."),
 "CorpusUnextracted": ("Corpus", "database/corpus.py", FUNNEL,
   "Converted minus extracted. One paper exhausted its rate-limit retries, so the corpus and the "
   "database differ by one and both numbers are reported."),
 "CorpusElsevierXml": ("Corpus", "database/corpus.py", FUNNEL, "Obtained as Elsevier full-text XML."),
 "CorpusPdf": ("Corpus", "database/corpus.py", FUNNEL, "Obtained as PDF: Wiley and Springer under entitlement, the rest open access."),
 "CorpusEuropePmc": ("Corpus", "database/corpus.py", FUNNEL, "Obtained as Europe PMC JATS deposits."),
 "CorpusOtherSource": ("Corpus", "database/corpus.py", FUNNEL, "Obtained by no other named route."),
 "FunnelDroppedPolymer": ("Corpus", "database/corpus.py", FUNNEL, "Dropped: no polymer named."),
 "FunnelDroppedRoute": ("Corpus", "database/corpus.py", FUNNEL, "Dropped: no depolymerisation route named."),
 "FunnelDroppedOffTopic": ("Corpus", "database/corpus.py", FUNNEL, "Dropped: off-topic subject or a review."),
 "FunnelPassRate": ("Corpus", "database/corpus.py", FUNNEL, "Share of candidates surviving the filter."),

 # --- the extraction run ----------------------------------------------------------------
 "DatabasePapers": ("Extraction", "database/corpus.py", MASS, "Papers the extractor processed."),
 "DatabaseYielding": ("Extraction", "database/corpus.py", MASS, "Papers that produced at least one record."),
 "DatabaseEmpty": ("Extraction", "database/corpus.py", MASS,
   "Papers that produced none. Mostly reviews and enzymatic work, i.e. papers that should yield "
   "none -- but this is also the audit's blind spot, since a missed experiment is invisible."),
 "DatabaseRecords": ("Extraction", "database/corpus.py", MASS, "Records extracted across the whole corpus."),
 "DatabaseMedianRecords": ("Extraction", "database/corpus.py", MASS, "Median records per yielding paper."),
 "DatabaseLargestPaper": ("Extraction", "database/corpus.py", MASS, "Records from the single largest paper."),
 "DatabaseCost": ("Extraction", "database/corpus.py", MASS, "USD spent on the mass extraction."),
 "DatabaseShots": ("Extraction", "database/corpus.py", MASS, "Worked examples in the prompt for the shipped run."),

 # --- the judge on the database ---------------------------------------------------------
 "JudgeRecords": ("Judge", "database/verdicts.py", MASS, "Records the judge read. Equals DatabaseRecords; quoted separately where the sentence is about judging."),
 "JudgeAccepted": ("Judge", "database/verdicts.py", MASS, "Verdict 'correct': accepted with nothing changed."),
 "JudgeCorrected": ("Judge", "database/verdicts.py", MASS,
   "Rejected with a proposed replacement value. The record survives into the corrected database "
   "with those fields rewritten."),
 "JudgeDropped": ("Judge", "database/verdicts.py", MASS,
   "Rejected outright -- the judge set drop_record, so cli/release.py deletes the row rather than "
   "repairing it. Partitioned on that flag, because that is what the released files act on."),
 "JudgePassRate": ("Judge", "database/verdicts.py", MASS, "Accepted as a share of judged. The headline quality figure."),
 "JudgeCorrectedShare": ("Judge", "database/verdicts.py", MASS, "Corrected as a share of judged."),
 "JudgeDroppedShare": ("Judge", "database/verdicts.py", MASS, "Dropped as a share of judged."),
 "JudgeFieldFixes": ("Judge", "database/verdicts.py", MASS, "Field-level changes proposed, larger than JudgeCorrected because one record can carry several."),
 "CorrectedRecords": ("Judge", "database/verdicts.py", MASS, "Rows in the corrected database: judged minus dropped."),
 "FieldTopCount": ("Judge", "database/verdicts.py", MASS, "Corrections to the most-corrected field (catalyst mass)."),
 "FieldSecondCount": ("Judge", "database/verdicts.py", MASS, "Corrections to the second most-corrected field (solvent mass)."),
 "JudgeContextCap": ("Judge", "database/verdicts.py", MASS, "The judge model's context window, in tokens."),
 "JudgeOverContext": ("Judge", "database/verdicts.py", MASS, "Papers that exceeded that window. Zero, so no verdict was truncated."),
 "LargestJudgedTokens": ("Judge", "database/verdicts.py", MASS, "Tokens in the longest paper judged, against the cap above."),

 # --- provenance: can a number be traced to a sentence ----------------------------------
 "CitationsTotal": ("Provenance", "database/provenance.py", MASS, "Chunk citations across the database."),
 "CitationsResolved": ("Provenance", "database/provenance.py", MASS, "Citations pointing at a chunk that exists in the paper the record came from."),
 "CitationsTraceable": ("Provenance", "database/provenance.py", MASS, "Resolved as a share of all citations."),
 "CitationsUnresolved": ("Provenance", "database/provenance.py", MASS, "Citations resolving to nothing. Marked in the release, not dropped."),
 "CitationsUntraceable": ("Provenance", "database/provenance.py", MASS, "Unresolved as a share -- the complement of CitationsTraceable."),
 "CitationsCopied": ("Provenance", "database/provenance.py", MASS, "Unresolved because copied verbatim from a worked example in the prompt."),
 "CitationsNoMatch": ("Provenance", "database/provenance.py", MASS, "Unresolved and matching no chunk anywhere."),

 # --- chemistry: does the extracted data behave like chemistry --------------------------
 "RouteGlycolysis": ("Chemistry", "database/chemistry.py", MASS, "Records whose solvent implies glycolysis."),
 "RouteHydrolysis": ("Chemistry", "database/chemistry.py", MASS, "Records whose solvent implies hydrolysis."),
 "RouteMethanolysis": ("Chemistry", "database/chemistry.py", MASS, "Records whose solvent implies methanolysis."),
 "RouteOther": ("Chemistry", "database/chemistry.py", MASS, "Records whose solvent names no route, so no product is fixed."),
 "RouteNamedTotal": ("Chemistry", "database/chemistry.py", MASS, "The three named routes summed. With RouteOther it accounts for the corpus."),
 "DistinctCatalysts": ("Chemistry", "database/chemistry.py", MASS,
   "Distinct catalyst strings. Large and long-tailed, which is what defeats a grader comparing "
   "catalysts by spelling."),
 "ConversionCoverage": ("Chemistry", "database/chemistry.py", MASS, "Share of records reporting conversion. A ceiling on what the data can support."),
 "YieldOverHundred": ("Chemistry", "database/chemistry.py", MASS, "Records reporting a yield above 100%, which is impossible."),
 "IdentityPairs": ("Chemistry", "database/chemistry.py", MASS, "Records reporting both yield and conversion, so the identity can be tested."),
 "IdentityImpossible": ("Chemistry", "database/chemistry.py", MASS, "Of those, records with yield above conversion. An identity, not a correlation."),
 "WithinPaperRho": ("Chemistry", "database/withinpaper.py", MASS,
   "Median within-paper Spearman rho for temperature against yield. Positive, i.e. the expected "
   "chemistry, once each paper is compared only with itself."),
 "WithinPaperPapers": ("Chemistry", "database/withinpaper.py", MASS, "Papers with enough records to compute that correlation."),
 "WithinPaperPositive": ("Chemistry", "database/withinpaper.py", MASS, "Share of those papers where the correlation runs the predicted way."),
 "WithinPaperShare": ("Chemistry", "database/withinpaper.py", MASS, "Those papers as a share of all yielding papers."),
 "WithinPooledRho": ("Chemistry", "database/withinpaper.py", MASS,
   "The same correlation pooled across every paper: near zero. Pooling is the wrong operation on "
   "optimised experiments, and the contrast with WithinPaperRho is the point."),
 "WithinPooledN": ("Chemistry", "database/withinpaper.py", MASS, "Records behind the pooled figure."),

 # --- the curated reference table --------------------------------------------------------
 "CuratedExperiments": ("Curated benchmark", "_setup.py", CURATED,
   "Experiments in the hand-curated answer key, including the entries the supervisors confirmed "
   "in the rescue round. Every metric-grader score is computed against this."),
 "CuratedPapers": ("Curated benchmark", "_setup.py", CURATED, "Papers the curated table covers."),

 # --- the adjudication: the two graders against two chemists ----------------------------
 "AdjRecords": ("Adjudication", "human/adjudicated.py", ADJ, "Records the chemists ruled on."),
 "AdjJudgeFlagged": ("Adjudication", "human/adjudicated.py", ADJ, "Records the judge called incorrect."),
 "AdjMetricFlagged": ("Adjudication", "human/adjudicated.py", ADJ, "Records the metric grader called incorrect."),
 "AdjJudgeTruePositives": ("Adjudication", "human/adjudicated.py", ADJ, "Of the judge's flags, how many a chemist agreed were wrong."),
 "AdjMetricTruePositives": ("Adjudication", "human/adjudicated.py", ADJ, "Of the metric's flags, how many a chemist agreed were wrong."),
 "AdjJudgePrecision": ("Adjudication", "human/adjudicated.py", ADJ, "Judge precision. Censused, so it carries no sampling error."),
 "AdjJudgeRecall": ("Adjudication", "human/adjudicated.py", ADJ, "Judge recall. Weighted, and wide, because its denominator reaches into the sampled pool."),
 "AdjJudgeFone": ("Adjudication", "human/adjudicated.py", ADJ, "Judge F1. As wide as recall."),
 "AdjJudgeKappa": ("Adjudication", "human/adjudicated.py", ADJ, "Judge agreement with the chemists beyond chance. Low, because most records are correct."),
 "AdjMetricPrecision": ("Adjudication", "human/adjudicated.py", ADJ, "Metric precision."),
 "AdjMetricRecall": ("Adjudication", "human/adjudicated.py", ADJ, "Metric recall."),
 "AdjMetricFone": ("Adjudication", "human/adjudicated.py", ADJ, "Metric F1."),
 "AdjMetricKappa": ("Adjudication", "human/adjudicated.py", ADJ, "Metric agreement beyond chance."),
 "AdjPairs": ("Adjudication", "human/adjudicated.py", ADJ,
   "Discordant pairs: records where exactly one grader matched the chemists. The only records that "
   "say which grader is better."),
 "AdjFavourJudge": ("Adjudication", "human/adjudicated.py", ADJ, "Discordant pairs won by the judge."),
 "AdjFavourMetric": ("Adjudication", "human/adjudicated.py", ADJ, "Discordant pairs won by the metric."),
 "AdjMcNemarP": ("Adjudication", "human/adjudicated.py", ADJ, "McNemar exact p on those pairs. Every pair is censused, so this carries no sampling error."),
 "AdjJudgeWinRate": ("Adjudication", "human/adjudicated.py", ADJ, "Judge wins as a share of discordant pairs."),
 "AdjPriorPairs": ("Adjudication", "human/significance.py", "gold/golden_set.json",
   "Discordant pairs the earlier random round produced. Too few for any outcome to reach "
   "significance -- the reason this round censused disagreements instead."),
 "LabelledRecords": ("Adjudication", "_setup.py", "gold/golden_set.json", "Records in that earlier round."),
 "AdjPowerAtSixty": ("Adjudication", "human/adjudicated.py", ADJ, "Power to detect a judge right 60% of the time, at the pairs returned."),
 "AdjPowerAtSixtyFive": ("Adjudication", "human/adjudicated.py", ADJ, "Power at 65%."),
 "AdjPowerAtSeventy": ("Adjudication", "human/adjudicated.py", ADJ, "Power at 70%."),
 "AdjPowerAtSeventyFive": ("Adjudication", "human/adjudicated.py", ADJ, "Power at 75%."),
 "AdjPowerAtEighty": ("Adjudication", "human/adjudicated.py", ADJ, "Power at 80%."),
 "AdjAcceptedDrawn": ("Adjudication", "human/worklist.py", ADJ, "Records drawn from the both-accepted pool for the page."),
 "AdjAcceptedAnswered": ("Adjudication", "human/adjudicated.py", ADJ, "Of those, how many came back answered. The divisor for the weight."),
 "AdjAcceptedPool": ("Adjudication", "human/adjudicated.py", ADJ, "The pool those were drawn from."),
 "AdjAcceptedWeight": ("Adjudication", "human/adjudicated.py", ADJ, "What each answered record stands for: pool over answered."),
 "AdjMissRateBound": ("Adjudication", "human/adjudicated.py", ADJ,
   "Rule of three. No wrong record among the answered ones bounds the hidden rate at roughly this, "
   "which is why metric recall reads 1.00 with a wide lower bound."),
 "AdjDesignDisagree": ("Adjudication", "human/adjudicated.py", ADJ, "Records the page censused as grader disagreements."),
 "AdjBothFlagged": ("Adjudication", "human/adjudicated.py", ADJ, "Records the page censused because both graders flagged them."),
 "AdjDesignAccepted": ("Adjudication", "human/adjudicated.py", ADJ, "Records the page sampled from the both-accepted cell."),
 "AdjAcceptedReviewed": ("Adjudication", "human/adjudicated.py", ADJ, "Records in the both-accepted cell under today's verdicts."),
 "AdjAcceptedSampled": ("Adjudication", "human/adjudicated.py", ADJ, "In that cell both by design and today."),
 "AdjAcceptedMovedIn": ("Adjudication", "human/adjudicated.py", ADJ,
   "Censused on the page but in the accepted cell today, because the solvent-alias fix landed "
   "afterwards. They keep weight 1: they were never sampled."),
 "AdjNowDisagree": ("Adjudication", "human/adjudicated.py", ADJ, "Records the graders still disagree on under today's verdicts."),
 "AdjDecidedFresh": ("Adjudication", "human/adjudicated.py", ADJ, "Records a chemist actively decided."),
 "AdjCarriedOver": ("Adjudication", "human/adjudicated.py", ADJ, "Records carried in pre-filled from the rescue round and left alone."),

 # --- integrity: the questions a referee asks first --------------------------------------
 "ExemplarPool": ("Integrity", "human/integrity.py", BENCH, "Papers the prompt's worked examples are drawn from."),
 "ExemplarsInBenchmark": ("Integrity", "human/integrity.py", BENCH, "Of those, how many are also benchmark papers. Leakage if not zero."),
 "BenchmarkInCorpus": ("Integrity", "human/integrity.py", MASS, "Benchmark papers that also sit inside the mass corpus."),
 "AnnotatorsShared": ("Integrity", "human/integrity.py", ADJ, "Records both chemists touched."),
 "AnnotatorsIndependent": ("Integrity", "human/integrity.py", ADJ,
   "Of those, how many both actively decided rather than leaving a pre-fill. Zero here, so this "
   "round supports no inter-annotator agreement figure and none should be quoted."),
 "ConstraintRecords": ("Integrity", "human/integrity.py", MASS, "Records wrong on arithmetic alone."),
 "ConstraintFlagged": ("Integrity", "human/integrity.py", MASS, "Of those, how many the judge also flagged."),
 "ConstraintCaught": ("Integrity", "human/integrity.py", MASS, "Flagged as a share -- the judge's hit rate on records that are provably wrong."),
 "ConstraintOverHundredCaught": ("Integrity", "human/integrity.py", MASS, "Hit rate on yields above 100%."),
 "ConstraintOverConversionCaught": ("Integrity", "human/integrity.py", MASS, "Hit rate on yields above conversion."),

 # --- model and grader comparison on the curated papers ----------------------------------
 "MatrixShippedAll": ("Grader matrix", "curated/matrix.py", BENCH, "Judge-metric agreement for the shipped pair, over every record."),
 "MatrixShippedEvaluable": ("Grader matrix", "curated/matrix.py", BENCH, "The same, over records the metric could evaluate."),
 "MatrixEvaluableLow": ("Grader matrix", "curated/matrix.py", BENCH, "Lowest evaluable-record agreement of the nine cells."),
 "MatrixEvaluableHigh": ("Grader matrix", "curated/matrix.py", BENCH, "Highest."),
 "MatrixGapLow": ("Grader matrix", "curated/matrix.py", BENCH, "Smallest gap between all-record and evaluable-record agreement."),
 "MatrixGapHigh": ("Grader matrix", "curated/matrix.py", BENCH,
   "Largest. The gap exists because the metric marks surplus records wrong without looking at "
   "them, not because of chemistry."),
 "BenchLunaFone": ("Extractor benchmark", "curated/extractions.py", BENCH, "Luna F1 on the curated papers, averaged over repeats."),
 "BenchLunaSd": ("Extractor benchmark", "curated/extractions.py", BENCH, "Its spread across repeats -- wider than some gaps between models."),
 "BenchLunaRuns": ("Extractor benchmark", "curated/extractions.py", BENCH, "Repeats behind it."),
 "BenchLunaShots": ("Extractor benchmark", "curated/extractions.py", BENCH, "Worked examples used."),
 "BenchOssFone": ("Extractor benchmark", "curated/extractions.py", BENCH, "OSS F1."),
 "BenchOssSd": ("Extractor benchmark", "curated/extractions.py", BENCH, "OSS spread."),
 "BenchOssRuns": ("Extractor benchmark", "curated/extractions.py", BENCH, "OSS repeats."),
 "BenchOssShots": ("Extractor benchmark", "curated/extractions.py", BENCH, "OSS worked examples."),
 "BenchTerraFone": ("Extractor benchmark", "curated/extractions.py", BENCH, "Terra F1."),
 "BenchTerraSd": ("Extractor benchmark", "curated/extractions.py", BENCH, "Terra spread."),
 "BenchTerraRuns": ("Extractor benchmark", "curated/extractions.py", BENCH, "Terra repeats."),
 "BenchTerraShots": ("Extractor benchmark", "curated/extractions.py", BENCH, "Terra worked examples."),
 "BenchShots": ("Extractor benchmark", "curated/extractions.py", BENCH, "Worked examples the benchmark was scored at."),
 "BenchRepeats": ("Extractor benchmark", "curated/extractions.py", BENCH, "Repeats per arm."),
 "CostLuna": ("Extractor benchmark", "cost.py", BENCH, "USD to extract the curated papers with Luna."),
 "CostTerra": ("Extractor benchmark", "cost.py", BENCH, "The same with Terra, which scores lower and costs more."),

 # --- prompt ablations --------------------------------------------------------------------
 "ShotsDelta": ("Ablations", "curated/shots.py", BENCH, "F1 gain from one worked example over none."),
 "ShotsP": ("Ablations", "curated/shots.py", BENCH, "p for that gain."),
 "ShotsAnovaP": ("Ablations", "curated/shots.py", BENCH, "One-way ANOVA among the arms that have examples: nothing separates them."),
 "ShotsBest": ("Ablations", "curated/shots.py", BENCH, "Arm with the highest mean. One, which is why the database ships at one."),
 "ShotsComparisons": ("Ablations", "curated/shots.py", BENCH, "Pairwise comparisons available among the arms."),
 "ShotsBonferroni": ("Ablations", "curated/shots.py", BENCH, "Bonferroni-corrected alpha for that many comparisons."),
 "ShotsSmallestPairwise": ("Ablations", "curated/shots.py", BENCH, "Smallest pairwise p among them, against that alpha."),
 "SourceDelta": ("Ablations", "curated/source_tracking.py", BENCH, "F1 gain from requiring source citations."),
 "SourceCiting": ("Ablations", "curated/source_tracking.py", BENCH, "F1 with citations required."),
 "SourceCitingSd": ("Ablations", "curated/source_tracking.py", BENCH, "Its spread."),
 "SourceNot": ("Ablations", "curated/source_tracking.py", BENCH, "F1 without."),
 "SourceNotSd": ("Ablations", "curated/source_tracking.py", BENCH, "Its spread."),
 "SourceP": ("Ablations", "curated/source_tracking.py", BENCH, "p for the difference. Short of significance, reported as such."),
 "ThresholdAcceptGap": ("Ablations", "curated/thresholds.py", BENCH,
   "F1 left on the table by the accept threshold. Reported and not taken: moving it now, to "
   "maximise a score on the papers the score is computed from, is the tuning we claim not to do."),
 "ThresholdAcceptBest": ("Ablations", "curated/thresholds.py", BENCH, "Where the accept threshold would have peaked."),
 "ThresholdCatalystGap": ("Ablations", "curated/thresholds.py", BENCH, "The same for the catalyst gate."),
 "ThresholdCatalystBest": ("Ablations", "curated/thresholds.py", BENCH, "Where it would have peaked."),
 "ThresholdToleranceGap": ("Ablations", "curated/thresholds.py", BENCH, "The same for the numeric tolerance."),
 "ThresholdToleranceBest": ("Ablations", "curated/thresholds.py", BENCH, "Where it would have peaked."),

 # --- what happens when the answer key is grown from the extraction's own output ---------
 "GrowthCuratedPrecision": ("Answer-key growth", "human/growth.py", CURATED, "Precision against the curated key as it stands."),
 "GrowthCuratedFone": ("Answer-key growth", "human/growth.py", CURATED, "F1 against the same."),
 "GrowthVouchedExperiments": ("Answer-key growth", "human/growth.py", CURATED, "Key size after promoting judge-accepted records into it."),
 "GrowthVouchedAdded": ("Answer-key growth", "human/growth.py", CURATED, "How many that added."),
 "GrowthVouchedPrecision": ("Answer-key growth", "human/growth.py", CURATED, "Precision against the grown key."),
 "GrowthVouchedFone": ("Answer-key growth", "human/growth.py", CURATED,
   "F1 against it. Higher without a single extracted record changing, which is why a key grown "
   "from the extraction's own output overstates quality."),
 "GrowthAllExperiments": ("Answer-key growth", "human/growth.py", CURATED, "Key size after promoting every unmatched record."),
 "GrowthAllAdded": ("Answer-key growth", "human/growth.py", CURATED, "How many that added."),
 "GrowthAllPrecision": ("Answer-key growth", "human/growth.py", CURATED, "Precision against that key."),
 "GrowthAllFone": ("Answer-key growth", "human/growth.py", CURATED, "F1 against it."),

 # --- bookkeeping --------------------------------------------------------------------------
 "ArtifactHash": ("Bookkeeping", "tools/paper_numbers.py", "every bundle",
   "Hash over the config content-hashes of every run behind these numbers. Change a run and this "
   "changes, so the manuscript declares which artifact set it describes."),
}
