"""Where our collection sits against the dataset Gao et al. used to train their GNN.

Gao et al. (Green Chem. 2025, 27, 7357) assembled 372 ionic-liquid glycolysis experiments and
trained a graph neural network on them. It is the closest published comparator to this work, so
the useful question is not which is bigger but whether they cover the same ground.

Two spaces, because "coverage" means two different things:

  a  chemical space -- what the catalysts are. Every catalyst is described by the same RDKit
     descriptors (weight, lipophilicity, polar surface, charge, ring and heteroatom counts,
     metal content), standardised, then projected onto its first two principal components.

  b  condition space -- how the reactions were run: temperature, time, and solvent-to-PET
     ratio, the three conditions both datasets record in the same units.

PCA is only a way of drawing many columns on flat paper. It finds the two directions in which
the points spread out most and plots those, so nearby points are chemically similar and the
axes have no units of their own. Distances are meaningful; the numbers on the axes are not.

What the picture is for: Gao et al. sit inside one region of both spaces, because their study
is ionic liquids in glycolysis by design. This collection surrounds it -- four routes, metal
salts, acids and bases as well as ionic liquids -- but does not contain it: 54 of their 70
structures appear nowhere in ours. Neither supersedes the other.

    fig9_pca.py                artifacts/figures/fig9_pca.pdf and .png
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "figures"))
from _style import CYCLE, DIM, INK, NEUTRAL, RULE, WARN, plt
from core.paths import ARTIFACTS

OURS = ARTIFACTS / "release" / "pet_homogeneous_release.csv"
GAO = Path("/tmp/claude-1000/-home-enkhnyam-Documents-Dev-pet-depolymerisation-database"
           "/5e482367-1eaa-4b6c-a0b6-008a3d911228/scratchpad/gao.xlsx")

MINE, THEIRS = CYCLE[0], CYCLE[1]
DESCRIPTORS = ["MolWt", "MolLogP", "TPSA", "NumHDonors", "NumHAcceptors",
               "NumRotatableBonds", "HeavyAtomCount", "RingCount", "NumAromaticRings",
               "FractionCSP3", "NumHeteroatoms", "NumValenceElectrons"]
NONMETAL = {1, 2, 5, 6, 7, 8, 9, 10, 14, 15, 16, 17, 18,
            32, 33, 34, 35, 36, 51, 52, 53, 54, 85, 86}


def describe(smiles_list):
    """One descriptor row per SMILES; None where the structure will not parse."""
    from rdkit import Chem, RDLogger
    from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors
    RDLogger.DisableLog("rdApp.*")
    source = {}
    for name in DESCRIPTORS:
        for module in (Descriptors, Lipinski, Crippen, rdMolDescriptors):
            if hasattr(module, name):
                source[name] = getattr(module, name)
                break
    out = {}
    for smiles in {s for s in smiles_list if isinstance(s, str) and s.strip()}:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            continue
        row = {}
        for name in DESCRIPTORS:
            try:
                row[name] = float(source[name](mol))
            except Exception:
                row[name] = np.nan
        row["charge"] = float(Chem.GetFormalCharge(mol))
        row["metals"] = float(sum(a.GetAtomicNum() not in NONMETAL for a in mol.GetAtoms()))
        row["fragments"] = float(len(Chem.GetMolFrags(mol)))
        out[smiles] = row
    return out


def project(blocks):
    """Standardise, then project onto the first two principal components.

    Fitted on both datasets together -- fitting on one and projecting the other would put the
    comparison in a frame chosen by one side.
    """
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    stacked = pd.concat(blocks, axis=0)
    good = stacked.dropna()
    scaled = StandardScaler().fit_transform(good.values)
    pca = PCA(n_components=2, random_state=0)
    coords = pca.fit_transform(scaled)
    frame = pd.DataFrame(coords, columns=["pc1", "pc2"], index=good.index)
    return frame, pca.explained_variance_ratio_


def cloud(axis, points, colour, label, size=16, alpha=0.35):
    axis.scatter(points.pc1, points.pc2, s=size, alpha=alpha, linewidths=0,
                 color=colour, label=label, zorder=3)


def main() -> None:
    ours = pd.read_csv(OURS, low_memory=False)
    gao = pd.read_excel(GAO, sheet_name="Glycolysis_Final")

    # --- chemical space, one point per experiment so the picture shows how often each is used
    table = describe(list(ours.catalyst_smiles.dropna()) + list(gao.IL_smiles.dropna()))
    columns = DESCRIPTORS + ["charge", "metals", "fragments"]
    mine = pd.DataFrame([table[s] for s in ours.catalyst_smiles if s in table], columns=columns)
    theirs = pd.DataFrame([table[s] for s in gao.IL_smiles if s in table], columns=columns)
    mine.index = [("mine", i) for i in range(len(mine))]
    theirs.index = [("theirs", i) for i in range(len(theirs))]
    chem, chem_var = project([mine, theirs])

    # --- condition space, the three conditions both datasets record the same way
    a = pd.DataFrame({"t": ours.temperature_c, "time": ours.reaction_time_min,
                      "ratio": ours.solvent_amount_g / ours.PET_amount_g}).dropna()
    b = pd.DataFrame({"t": gao.temperature_c, "time": gao.reaction_time_min,
                      "ratio": gao.solvent_amount / gao.PET_amount}).dropna()
    for frame in (a, b):
        frame["time"] = np.log10(frame.time.clip(lower=1))
        frame["ratio"] = np.log10(frame.ratio.clip(lower=0.01))
    a = a[np.isfinite(a).all(axis=1)]
    b = b[np.isfinite(b).all(axis=1)]
    a.index = [("mine", i) for i in range(len(a))]
    b.index = [("theirs", i) for i in range(len(b))]
    cond, cond_var = project([a, b])

    plt.rcParams.update({"font.size": 10, "axes.labelsize": 10.5,
                         "xtick.labelsize": 9, "ytick.labelsize": 9})
    figure, axes = plt.subplots(1, 2, figsize=(11.4, 5.2))
    figure.subplots_adjust(top=0.615, bottom=0.13, left=0.065, right=0.985, wspace=0.22)

    for axis, points, variance, title, note in [
            (axes[0], chem, chem_var, "a   what the catalysts are",
             "RDKit descriptors of every catalyst structure"),
            (axes[1], cond, cond_var, "b   how the reactions were run",
             "temperature, time and solvent-to-PET ratio")]:
        mine_pts = points.loc[[i for i in points.index if i[0] == "mine"]]
        theirs_pts = points.loc[[i for i in points.index if i[0] == "theirs"]]
        cloud(axis, mine_pts, MINE, f"ours  ({len(mine_pts):,})", size=13, alpha=0.22)
        cloud(axis, theirs_pts, THEIRS, f"Gao et al.  ({len(theirs_pts):,})", size=20, alpha=0.55)
        axis.set_title(title, loc="left", fontsize=11, fontweight="bold", pad=22)
        axis.text(0, 1.035, note, transform=axis.transAxes, ha="left",
                  fontsize=9, color=DIM)
        axis.set_xlabel(f"first principal component  ({100 * variance[0]:.0f}% of the spread)")
        axis.set_ylabel(f"second  ({100 * variance[1]:.0f}%)")
        axis.legend(loc="upper right", markerscale=1.8, handletextpad=0.3, framealpha=0.9)
        axis.grid(color=RULE, lw=0.5, alpha=0.4, zorder=0)
        axis.set_axisbelow(True)

    figure.text(0.008, 0.925,
                "Our collection surrounds the published IL dataset without containing it",
                fontsize=14.5, fontweight="bold", color=INK)
    figure.text(0.008, 0.775,
                "Gao et al. (Green Chem. 2025) trained a graph neural network on 372 "
                "ionic-liquid glycolysis experiments. Both datasets are described by the same\n"
                "features and drawn on the same axes. Their study occupies one region by "
                "design — ionic liquids, glycolysis only — while ours spans four routes and "
                "five catalyst classes.\n"
                "But it is not a superset: 54 of their 70 catalyst structures appear nowhere "
                "in ours, and only 16 are shared.",
                fontsize=10.5, color=DIM, linespacing=1.6, va="bottom")

    out = ARTIFACTS / "figures" / "fig9_pca.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out)
    figure.savefig(out.with_suffix(".png"), dpi=220)
    plt.close(figure)
    print(f"wrote {out.relative_to(ROOT)} and .png")
    print(f"  chemical space  ours {len(mine):,} vs Gao {len(theirs):,}   "
          f"PC1+PC2 = {100 * chem_var.sum():.0f}% of the spread")
    print(f"  condition space ours {len(a):,} vs Gao {len(b):,}   "
          f"PC1+PC2 = {100 * cond_var.sum():.0f}%")


if __name__ == "__main__":
    main()
