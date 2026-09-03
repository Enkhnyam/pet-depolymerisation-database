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


def condition_space(frame: pd.DataFrame) -> dict:
    """Temperature against yield, ours and the hand curation's, on the papers both cover.

    Both sets come from the same 19 papers, which is the whole point. Our full glycolysis
    corpus against Gao's 19-paper set shows a large cloud containing a small one, and would look
    the same if we had extracted nothing from their papers at all.
    """
    ours = frame[frame.category.isin(["both", "ours"])]
    curated = frame[frame.category != "ours"]
    return {
        "this work": ours[["ours_temperature_c", "ours_yield_percent"]].dropna()
                         .set_axis(["temperature_c", "yield_percent"], axis=1),
        "hand-curated": curated[["gao_temperature_c", "gao_yield_percent"]].dropna()
                         .set_axis(["temperature_c", "yield_percent"], axis=1),
    }


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
        "identical": identical(frame),
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

    show("agreement on the records both datasets hold", result["agreement"])
    print("\n  glycolysis only: Gao curated no hydrolysis or methanolysis, so nothing here "
          "\n  transfers to them. database/withinpaper.by_route() is what does.")


if __name__ == "__main__":
    main()
