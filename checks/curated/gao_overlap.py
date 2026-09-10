"""Our automatic extraction against Gao et al.'s hand-curated ionic-liquid glycolysis set.

Gao et al. (Green Chem. 2025, 27, 7357) curated 364 PET glycolysis experiments by hand from 19
papers, for a graph neural network. It is the only external reference this project has, and the
only one it will get: nobody has hand-curated hydrolysis or methanolysis at that scale.

Three questions, in the order a referee asks them.

  Is the extraction missing data?  No. On the papers both cover, the pipeline found more
      experiments than our own team did reading the same papers by hand, and where the two
      describe the same experiment they agree on most fields.

  Then why does Gao list more?  Because 173 of their 364 records -- 48% -- are values read off
      a chart. We instruct the model to read tables and ignore figures, so it never collected
      them. A further 30 sit in Supporting Information we do not hold, and 18 are
      response-surface design tables our scope rules skip. That leaves 12 records, 3% of Gao's
      set, in a table we read and did not pick up. That is the real extraction shortfall.

  Does any of this say anything about the other two routes?  No, and it cannot. Gao is
      glycolysis only, so this check's reach stops there. The argument that carries to
      hydrolysis and methanolysis is database/withinpaper.by_route(), which needs no external
      reference at all.

The classification of all 364 is human work: an automatic rule proposed a reason for each and a
chemist reading the paper settled the ones it got wrong. `rule_said` is the proposal, `category`
is the verdict. Both are in the file, so the disagreement rate is visible rather than asserted.

    gao_overlap.py
"""
import pandas as pd

from _setup import TOLERANCE, show, sources
from core.evaluation import _penalty_numeric
from core.paths import data_path
from core.schema import canonical_solvent

GAO = "gao/record_classification.csv"
PAPERS = "gao/paper_dois.csv"

# Ionic liquids are written two ways and mean one thing: Gao writes [BMIM]Br and [BMIM]2CoCl4,
# we write [Bmim][Br] and [bmim]2[CoCl4]. Comparing those strings measures bracket convention,
# not chemistry -- the same argument core.schema makes for solvent names, where "EG" against
# "ethylene glycol" was spending a tenth of the metric's accept budget on spelling.
#
# Deliberately shallow: case, brackets, whitespace, and the one alias where a paper's "Ac" is
# everyone else's "OAc". A name naming two components -- Gao's [BMIM]Cu(Ac)3 against our
# Cu(OAc)2-[Bmim][OAc] -- is left as a disagreement, because deciding whether those are one
# substance or two is chemistry and not a string operation.
BRACKETS = str.maketrans("", "", "[] ")

# Read off the solvent, so a comparison of numbers is not also a comparison of spellings.
NUMERIC = ["temperature_c", "reaction_time_min", "catalyst_amount_g", "PET_amount_g",
           "solvent_amount_g", "yield_percent", "conversion_percent", "selectivity_percent"]
TEXT = ["catalyst", "solvent"]

# The five reasons a Gao record is or is not in ours, in the order the argument uses them.
REASONS = ["both", "chart", "si", "rule", "missed"]
SHORT = {"both": "in both", "chart": "Gao only: read off a chart",
         "si": "Gao only: in Supporting Information we lack",
         "rule": "Gao only: a design table we skip",
         "missed": "Gao only: in a table we read", "ours": "ours only"}


def records() -> pd.DataFrame:
    return pd.read_csv(data_path(GAO), low_memory=False)


def agreement(frame: pd.DataFrame) -> pd.DataFrame:
    """Per field, how often our value and Gao's agree on the records both hold.

    Numeric fields go through core.evaluation._penalty_numeric at the same tolerance the metric
    grader uses, so "agrees" means here exactly what it means everywhere else in the project.
    Text fields go through canonical_solvent first: "EG" against "ethylene glycol" is a spelling
    difference, not a disagreement about chemistry.
    """
    both = frame[frame.category == "both"]
    rows = []
    for field in NUMERIC:
        pair = both[[f"gao_{field}", f"ours_{field}"]].dropna()
        agree = sum(_penalty_numeric(g, o, TOLERANCE) == 0
                    for g, o in pair.itertuples(index=False))
        rows.append({"field": field, "both report it": len(pair),
                     "agree": agree, "share": agree / len(pair) if len(pair) else float("nan")})
    for field in TEXT:
        pair = both[[f"gao_{field}", f"ours_{field}"]].dropna()
        same = [(canonical_name(g), canonical_name(o)) for g, o in pair.itertuples(index=False)]
        agree = sum(g == o for g, o in same)
        rows.append({"field": field, "both report it": len(pair),
                     "agree": agree, "share": agree / len(pair) if len(pair) else float("nan")})
    return pd.DataFrame(rows).set_index("field")


def canonical_name(name) -> str:
    """A catalyst or solvent name reduced to one spelling, so a comparison tests the substance."""
    text = canonical_solvent(name).translate(BRACKETS)
    return text.replace("(ac)", "(oac)").replace("ac", "oac").replace("ooac", "oac")


# ---------------------------------------------------------------------------------------------
# The other direction: the 91 records we hold on these papers that Gao does not.
#
# Gao's side of the gap has been sorted into reasons since this check was written; ours was a
# single bucket labelled "ours only", which is not an answer to the question a referee actually
# asks -- if the extraction found more, more of *what*?
# ---------------------------------------------------------------------------------------------

# Notation for one substance that canonical_name() does not reach. Case, brackets and the Ac/OAc
# alias it handles; these are the four kinds left, and each was settled by reading the paper.
#
#   dimim/dmim, m-O/O   two spellings of dimethylimidazolium and of a mu-oxo bridge.
#   spelled out         the paper's own name against Gao's abbreviation.
#   components/product  we name what was mixed, Gao names what came out. 10.1016/
#                       j.polymdegradstab.2021.109601 mixes [TMG]Cl with ZnCl2 1:1 and confirms
#                       ZnCl3- by ESI-MS; 10.1016/j.polymdegradstab.2014.10.005 mixes equimolar
#                       Cu(OAc)2 with [Bmim][OAc] and confirms the Cu-O bond by Raman. One
#                       substance each, on the papers' own evidence. agreement() above still
#                       declines to make this call, and is right to: it is a fact about two
#                       named papers, not a string operation.
SAME_SUBSTANCE = {"1,3-dimethylimidazolium acetate": "[DMIM]Ac",
                  "[TMG]Cl/ZnCl2": "[TMG]ZnCl3",
                  "[C6 TMG]Cl/2ZnCl2": "[C6TMG](ZnCl3)2",
                  "Cu(OAc)2-[Bmim][OAc]": "[BMIM]Cu(Ac)3",
                  "Zn(OAc)2-[Bmim][OAc]": "[BMIM]Zn(Ac)3"}

NOT_IONIC = {"none", "FeCl3"}          # Gao's set is ionic liquids; a blank or a bare salt is not

CONDITIONS = ["temperature_c", "reaction_time_min", "catalyst_amount_g",
              "PET_amount_g", "solvent_amount_g"]
CONDITION_SLACK = 0.02                 # same run, allowing for each side's rounding

# Two of our rows carrying identical numbers are either one experiment recorded twice or two real
# experiments that came out the same, and our schema cannot tell which: it has no field for
# "which recycle cycle" or "which table of the paper". Settled by reading the five papers where
# it happens, and each entry is a table reference that can be checked.
IDENTICAL_ROWS_ARE = {
    "10.1002/app.38706": "repeat",              # Table III, seven recycle cycles at 80.1-80.7
    "10.1021/sc5007522": "repeat",              # the recycling table, cycle 0 at 81.1
    "10.1039/c8nj06090h": "tabulated twice",    # Table 3 restates Table 1 entries 1 and 2
    "10.1016/j.polymdegradstab.2021.109601": "tabulated twice",   # a summary table and a
                                                # literature comparison both restate 84.5 / 92.7
    "10.1021/acssuschemeng.0c04108": "tabulated twice",   # no second table found; counted
                                                # against us rather than explained away
}

OURS_ONLY_REASONS = ["a catalyst Gao did not curate", "a condition Gao did not curate",
                     "a repeat of a run Gao curated once", "the same run tabulated twice",
                     "not an ionic liquid", "the same run, our matcher missed it"]


def substance(name) -> str:
    """A catalyst name reduced far enough that the two datasets' spellings of one liquid meet."""
    if not isinstance(name, str):
        return ""
    text = canonical_name(SAME_SUBSTANCE.get(name.strip(), name))
    return text.translate(str.maketrans("", "", "()")).replace("dimim", "dmim").replace("m-o", "o")


def _same(left, right, left_side, right_side, fields, slack=CONDITION_SLACK) -> bool:
    """Every field both rows report agrees. A blank on either side is missing data, not a clash.

    `slack` of zero means byte-identical, which is the test for one of our rows duplicating
    another: an extractor that reads a table twice writes the same digits twice, while a
    recycling series differs in the third. At one shared tolerance the two questions are the
    same question, and asking it that way filed a whole recycling table as duplication.
    """
    shared = [f for f in fields
              if pd.notna(left[left_side + f]) and pd.notna(right[right_side + f])]
    return bool(shared) and all(
        abs(left[left_side + f] - right[right_side + f])
        <= slack * max(abs(left[left_side + f]), abs(right[right_side + f]), 1e-9)
        for f in shared)


def ours_only(frame: pd.DataFrame) -> pd.DataFrame:
    """Each record we hold and Gao does not, with the reason it is not in their table."""
    mine = frame[frame.category == "ours"]
    theirs = frame[frame.category != "ours"]
    everything = CONDITIONS + OUTCOMES
    rows = []
    for position, record in mine.iterrows():
        ours_here = frame[frame.category.isin(["both", "ours"]) & (frame.doi == record.doi)
                          & (frame.index != position)]
        twins = theirs[(theirs.doi == record.doi)
                       & (theirs.gao_catalyst.map(substance) == substance(record.ours_catalyst))]
        # Identical on every field, including which fields are blank: comparing only the fields
        # both rows fill made a row that omits a yield a duplicate of every row that has one.
        identical = any(
            substance(other.ours_catalyst) == substance(record.ours_catalyst)
            and [f for f in everything if pd.isna(other["ours_" + f])]
                == [f for f in everything if pd.isna(record["ours_" + f])]
            and _same(other, record, "ours_", "ours_", everything, slack=0.0)
            for _, other in ours_here.iterrows())
        curated_run = [g for _, g in twins.iterrows()
                       if _same(g, record, "gao_", "ours_", CONDITIONS)]
        # Same conditions, same outcomes, and yet Gao's row is filed as one of theirs alone.
        # Both sides describe one experiment and the pair fell outside the matcher: the catalyst
        # is written two ways, and Gao's numbers are round -- 40.0, 45.0, 42.0 against our 39.8,
        # 45.6, 42.7 -- which is what reading a figure looks like beside reading the table. The
        # chart label on their row is right; what is wrong is calling ours a record they lack.
        gao_lists_it = [g for g in curated_run
                        if g.category != "both" and _same(g, record, "gao_", "ours_", OUTCOMES)]

        if str(record.ours_catalyst) in NOT_IONIC:
            reason = "not an ionic liquid"
        elif identical:
            reason = ("a repeat of a run Gao curated once"
                      if IDENTICAL_ROWS_ARE.get(record.doi) == "repeat"
                      else "the same run tabulated twice")
        elif not len(twins):
            reason = "a catalyst Gao did not curate"
        elif gao_lists_it:
            reason = "the same run, our matcher missed it"
        elif curated_run:
            # Gao's row at these settings is already matched to a different record of ours, so
            # this is a further measurement at the same settings -- a recycle cycle, a replicate.
            reason = "a repeat of a run Gao curated once"
        else:
            reason = "a condition Gao did not curate"
        rows.append({"doi": record.doi, "catalyst": record.ours_catalyst, "reason": reason})
    return pd.DataFrame(rows)


# The three outcome fields share a 0-100 axis, so they can be compared on one parity panel
# without normalising anything.
OUTCOMES = ["yield_percent", "conversion_percent", "selectivity_percent"]
PARITY_SLACK = 2.0     # percentage points; these are all percentages, so absolute, not relative


def parity(frame: pd.DataFrame) -> pd.DataFrame:
    """Gao's value beside ours for every matched record, long-form, one row per pair.

    Only the records both datasets describe -- same paper, same experiment. An overlay of two
    whole datasets is not this: our corpus holds 2,531 glycolysis records from 337 papers
    against Gao's 364 from 19, and drawing those on one axis shows that a large cloud contains
    a small one, which would be true even if we had extracted nothing from their papers.
    """
    both = frame[frame.category == "both"]
    rows = []
    for field in OUTCOMES:
        pair = both[["doi", f"gao_{field}", f"ours_{field}"]].dropna()
        for doi, theirs, mine in pair.itertuples(index=False):
            rows.append({"field": field, "doi": doi, "gao": theirs, "ours": mine})
    frame = pd.DataFrame(rows)
    frame["agrees"] = (frame.gao - frame.ours).abs() <= PARITY_SLACK
    return frame


def identical(frame: pd.DataFrame) -> pd.DataFrame:
    """Per field, how many matched pairs carry byte-identical values."""
    both = frame[frame.category == "both"]
    rows = []
    for field in NUMERIC:
        pair = both[[f"gao_{field}", f"ours_{field}"]].dropna()
        same = int((pair.iloc[:, 0] == pair.iloc[:, 1]).sum())
        rows.append({"field": field, "pairs": len(pair), "identical": same,
                     "share": same / len(pair) if len(pair) else float("nan")})
    return pd.DataFrame(rows).set_index("field")


# Two quantities a chemist compares that neither dataset stores: loading and dilution are
# ratios, and a raw mass says nothing without the PET it was charged against.
DERIVED = {
    "catalyst_loading_wt": ("catalyst_amount_g", "PET_amount_g", 100.0),
    "solvent_ratio": ("solvent_amount_g", "PET_amount_g", 1.0),
}

# Which axes span decades. A kernel density on raw grams is decided by whichever record used a
# kilogram of PET; on log grams it describes the bulk.
LOG_AXES = {"reaction_time_min", "catalyst_amount_g", "PET_amount_g", "solvent_amount_g",
            "catalyst_loading_wt", "solvent_ratio"}


def _column(frame: pd.DataFrame, prefix: str, field: str) -> pd.Series:
    """One field for one side of the comparison, deriving it if it is a ratio."""
    if field in DERIVED:
        top, bottom, scale = DERIVED[field]
        return scale * frame[f"{prefix}{top}"] / frame[f"{prefix}{bottom}"].replace(0, pd.NA)
    return frame[f"{prefix}{field}"]


def extra_records(frame: pd.DataFrame) -> pd.DataFrame:
    """How complete the records only this work holds are, against the ones both datasets hold.

    The obvious suspicion about an extraction that returns more records than a person did is
    that the surplus is junk -- fragments, duplicates, rows misread out of a table. This is the
    test of it, and it passes: the 91 records hand curation does not have report their fields at
    the same rate as the 131 both datasets share, better on temperature and reaction time, and
    they come from 13 of the 19 papers rather than from one anomalous document.

    The two mass fields are the exception and are the same two the judge corrects most often,
    which is consistent with what those records are: runs stated in a results table whose
    absolute charges are given once in a methods paragraph.
    """
    extra = frame[frame.category == "ours"]
    shared = frame[frame.category == "both"]
    rows = []
    for field in NUMERIC + TEXT:
        rows.append({
            "field": field,
            "shared": _column(shared, "ours_", field).notna().mean(),
            "ours only": _column(extra, "ours_", field).notna().mean(),
        })
    table = pd.DataFrame(rows).set_index("field")
    table.attrs["extra"] = len(extra)
    table.attrs["shared"] = len(shared)
    table.attrs["extra papers"] = int(extra.doi.nunique())
    table.attrs["papers"] = int(frame.doi.nunique())
    return table


def disagreements(frame: pd.DataFrame) -> pd.DataFrame:
    """Every numeric value both datasets report, and how far apart the two are.

    The agreement table says how often the two agree at the grader's tolerance. It cannot say
    what a disagreement looks like, and the answer turns out to be the interesting part: of 842
    values reported by both, 797 are identical to the digit -- temperature and reaction time on
    every one of the 118 records that carry them -- and the 45 that differ are almost all masses,
    apart by factors rather than by percent. Catalyst mass disagreements have a median relative
    difference of 40% and a maximum of 669%; PET and solvent masses sit at 100%, which is a
    factor of two.

    That is the same failure this project's judge concentrates its corrections on, arrived at
    from the outside: authors state an absolute charge once and vary it implicitly as a ratio,
    and whichever reader misses that -- person or model -- lands a factor out. It is the
    strongest external corroboration available for the error profile the judge reports.
    """
    both = frame[frame.category == "both"]
    rows = []
    for field in NUMERIC:
        theirs = pd.to_numeric(_column(both, "gao_", field), errors="coerce")
        ours = pd.to_numeric(_column(both, "ours_", field), errors="coerce")
        keep = theirs.notna() & ours.notna()
        for a, b in zip(theirs[keep], ours[keep]):
            # The ratio of the larger to the smaller, not the relative difference: "a factor
            # of two" is what these disagreements are, and a reader converting 100% into that
            # in their head is a reader the axis has failed.
            ratio = (max(abs(a), abs(b)) / min(abs(a), abs(b))
                     if min(abs(a), abs(b)) else float("nan"))
            rows.append({"field": field, "gao": a, "ours": b,
                         "identical": a == b, "ratio": ratio,
                         "relative": abs(b - a) / abs(a) if a else float("nan")})
    return pd.DataFrame(rows)


def reclassification(frame: pd.DataFrame) -> pd.DataFrame:
    """What the automatic rule proposed for each record, against what a chemist settled on.

    The five reasons in the accounting are human verdicts, and this is the audit of them. It
    matters most in one direction: the rule proposed "our extraction missed it" for 20 records
    and a person reading the papers confirmed 11 of them, moving six to values plotted rather
    than tabulated and three to design tables our scope skips. Reported automatically, this
    comparison would have blamed the extraction for nearly twice as many records as it deserves,
    which is the reason the classification is human work and is worth showing rather than
    asserting.
    """
    gao = frame[frame.category != "ours"]
    return pd.DataFrame({
        "the rule proposed": gao.rule_said.value_counts(),
        "a chemist settled on": gao.category.value_counts(),
    }).reindex(REASONS).fillna(0).astype(int)


def per_paper(frame: pd.DataFrame) -> pd.DataFrame:
    """Records each side holds, paper by paper.

    The size difference is reported as one total and as five reasons, and neither says whether
    it is spread across the corpus or concentrated in a few papers. It matters: 173 records read
    off a chart are one kind of problem if they come from every paper and another kind if two
    papers plotted everything they did.
    """
    gao = frame[frame.category != "ours"].groupby("doi").size().rename("hand-curated")
    ours = frame[frame.category.isin(["both", "ours"])].groupby("doi").size().rename("this work")
    return pd.concat([gao, ours], axis=1).fillna(0).astype(int)


def completeness(frame: pd.DataFrame) -> pd.DataFrame:
    """How often each side fills each field, on its own records.

    The section compares where the two datasets agree and why they differ in size. It never
    asked the third question, which is whether an extraction reports as much per record as a
    person does: hand curation fills every condition field on every record, and this extraction
    fills 84 to 97% of them. Selectivity is the widest gap and the least surprising one, since
    it is the field the source papers report least consistently.
    """
    gao = frame[frame.category != "ours"]
    ours = frame[frame.category.isin(["both", "ours"])]
    rows = []
    for field in NUMERIC + TEXT:
        rows.append({
            "field": field,
            "hand-curated": _column(gao, "gao_", field).notna().mean(),
            "this work": _column(ours, "ours_", field).notna().mean(),
        })
    return pd.DataFrame(rows).set_index("field")


def condition_space(frame: pd.DataFrame, x: str = "temperature_c",
                    y: str = "yield_percent") -> dict:
    """Two fields, ours and the hand curation's, on the papers both cover.

    Both sets come from the same 19 papers, which is the whole point. Our full glycolysis corpus
    against Gao's 19-paper set shows a large cloud containing a small one, and would look the
    same if we had extracted nothing from their papers at all.

    Log axes are taken here rather than in the figure, so the density is estimated on the scale
    it is drawn on. Estimating on grams and then plotting the log of the result would describe a
    different distribution from the one on the page.
    """
    sides = {"this work": ("ours_", frame[frame.category.isin(["both", "ours"])]),
             "hand-curated": ("gao_", frame[frame.category != "ours"])}
    found = {}
    for label, (prefix, part) in sides.items():
        pair = pd.DataFrame({x: _column(part, prefix, x), y: _column(part, prefix, y)})
        pair = pair.apply(pd.to_numeric, errors="coerce").dropna()
        for field in (x, y):
            if field in LOG_AXES:
                pair = pair[pair[field] > 0]
                pair[field] = pair[field].apply(lambda v: __import__("math").log10(v))
        found[label] = pair
    return found


def compute() -> dict:
    frame = records()
    papers = pd.read_csv(data_path(PAPERS))
    gao = frame[frame.category != "ours"]
    split = frame.category.value_counts()

    # Papers counted from the classification, which carries a DOI on every record.
    # paper_dois.csv is the identification work and is one revision behind it: 22 label rows, 6
    # of them still unresolved and two pairs that turned out to be one paper split in two.
    return {
        "records": frame,
        "split": split.reindex(REASONS).fillna(0).astype(int),
        "agreement": agreement(frame),
        "parity": parity(frame),
        "condition space": condition_space(frame),
        "completeness": completeness(frame),
        "per paper": per_paper(frame),
        "reclassification": reclassification(frame),
        "disagreements": disagreements(frame),
        "extra records": extra_records(frame),
        "identical": identical(frame),
        "ours only": ours_only(frame).reason.value_counts()
                     .reindex(OURS_ONLY_REASONS).fillna(0).astype(int),
        "counts": {
            "Gao records": len(gao),
            "Gao papers": int(gao.doi.nunique()),
            "labels still unidentified": int(papers.doi.isna().sum()),
            "records we hold on those papers": int((frame.category.isin(["both", "ours"])).sum()),
            "shared records": int((frame.category == "both").sum()),
            "ours alone": int((frame.category == "ours").sum()),
        },
        # the one number the limitations section has to quote
        "true miss": int(split.get("missed", 0)),
        "true miss share": split.get("missed", 0) / len(gao),
        "chart share": split.get("chart", 0) / len(gao),
        # how often the automatic rule needed a person to overrule it, and in which direction:
        # nine of the fourteen were the rule calling something our miss and a chemist deciding
        # it was chart-read or a design table, so the shortfall is human-reduced not inflated
        "reclassified": int((gao.rule_said.notna() & (gao.rule_said != gao.category)).sum()),
        "reclassified from missed": int(((gao.rule_said == "missed")
                                         & (gao.category != "missed")).sum()),
    }


def main() -> None:
    sources(gao=GAO, crosswalk=PAPERS)
    result = compute()

    show("what the two datasets hold", result["counts"], fmt="{:.0f}")

    labelled = result["split"].rename(index=SHORT)
    show("every one of Gao's records, by why it is or is not in ours", labelled, fmt="{:.0f}")
    print(f"\n  {result['chart share']:.0%} of Gao's set is read off a chart, which we instruct "
          f"the model not to do")
    print(f"  {result['true miss']} records ({result['true miss share']:.1%}) are the real "
          f"extraction shortfall")
    print(f"  {result['reclassified']} of the automatic reasons were overruled by a chemist")

    show("every record we hold and Gao does not, by why they have no counterpart",
         result["ours only"], fmt="{:.0f}")

    show("agreement on the records both datasets hold", result["agreement"])
    print("\n  glycolysis only: Gao curated no hydrolysis or methanolysis, so nothing here "
          "\n  transfers to them. database/withinpaper.by_route() is what does.")


if __name__ == "__main__":
    main()
