"""Figure 1 -- what was built: corpus to database.

Numbers come from checks/database/{corpus,chemistry,provenance}.py, which print the same values.
"""
import pandas as pd

from _style import DIM, ROUTE, WARN, bars, canvas, heatmap, note, save
from database import chemistry as chem
from database import corpus as corpus_check
from database import provenance as prov_check

REACHABLE = "#0E7C6B"
UNREACHABLE = "#C9D6D3"


def funnel(axis, stages: dict) -> None:
    """The four surviving counts, with the drops annotated between them."""
    short = {"candidates found": "searched", "passed the filter": "relevant",
             "of those, Elsevier": "reachable", "converted to chunked text": "converted",
             "extracted so far": "extracted"}
    keep = {short.get(k, k): v for k, v in stages.items() if not k.startswith("dropped")}
    bars(axis, pd.Series(keep), colour=REACHABLE, xlabel="", ylabel="papers",
         title="search to corpus")
    axis.tick_params(axis="x", labelrotation=30)
    for position, value in enumerate(keep.values()):
        axis.text(position, value, f"{value:,}", ha="center", va="bottom", fontsize=5.8, color=DIM)


def main() -> None:
    corpus = corpus_check.compute()
    chemistry = chem.compute()
    provenance = prov_check.compute()
    frame = chemistry["records"]

    figure, panel = canvas(2, 4, width=9.2, height=4.8)

    funnel(panel[0], corpus["funnel"])

    publishers = corpus["publishers"]
    colours = [REACHABLE if name == "Elsevier" else UNREACHABLE for name in publishers.index]
    panel[1].bar(range(len(publishers)), publishers.values, color=colours, width=0.72)
    panel[1].set_xticks(range(len(publishers)), publishers.index)
    panel[1].tick_params(axis="x", labelrotation=35)
    panel[1].set_ylabel("relevant papers")
    panel[1].set_title(f"{panel[1].get_title(loc='left')}   only Elsevier is reachable",
                       loc="left", fontsize=7.5)

    per_paper = corpus["per paper"]
    panel[2].hist(per_paper, bins=range(1, 42), color=REACHABLE)
    panel[2].set_xlabel("records per paper")
    panel[2].set_ylabel("papers")
    note(panel[2], f"median {per_paper.median():.0f} · longest {per_paper.max():.0f}",
         colour=DIM, x=0.97, y=0.9, ha="right")

    empty = corpus["empty papers"]
    bars(panel[3], empty, colour=UNREACHABLE, horizontal=True, xlabel="papers",
         title=f"{int(empty.sum())} papers yielded nothing")

    routes = chemistry["by route"]["records"].sort_values(ascending=False)
    panel[4].bar(range(len(routes)), routes.values, width=0.72,
                 color=[ROUTE.get(name, DIM) for name in routes.index])
    panel[4].set_xticks(range(len(routes)), [str(i).replace("other/unclear", "unclear")
                                             for i in routes.index])
    panel[4].tick_params(axis="x", labelrotation=30)
    panel[4].tick_params(axis="x", labelrotation=35)
    panel[4].set_ylabel("records")

    fields = ["catalyst", "solvent", "reaction_time_min", "temperature_c", "PET_amount_g",
              "catalyst_amount_g", "yield_percent", "conversion_percent", "solvent_amount_g",
              "pressure_atm", "selectivity_percent"]
    coverage = pd.Series({f.replace("_percent", " %").replace("_", " "): frame[f].notna().mean()
                          for f in fields})
    bars(panel[5], coverage * 100, colour=REACHABLE, horizontal=True,
         xlabel="% of records reporting it", title="field completeness")

    top = frame.catalyst.value_counts().head(12)
    bars(panel[6], top, colour=REACHABLE, horizontal=True, xlabel="records",
         title=f"{frame.catalyst.nunique()} distinct names")

    citations = provenance["counts"]
    resolved = pd.Series({"resolve": citations["resolve to the paper's own text"],
                          "from a demo": citations["copied from a worked example"],
                          "match nothing": citations["match no chunk anywhere"]})
    panel[7].bar(range(len(resolved)), resolved.values, width=0.72,
                 color=[REACHABLE, "#9A6510", WARN])
    panel[7].set_xticks(range(len(resolved)), resolved.index)
    panel[7].tick_params(axis="x", labelrotation=35)
    panel[7].set_ylabel("chunk citations")
    panel[7].set_title(f"{panel[7].get_title(loc='left')}   "
                       f"{provenance['traceable']:.1%} traceable", loc="left", fontsize=7.5)

    save(figure, "fig1_database")


if __name__ == "__main__":
    main()
