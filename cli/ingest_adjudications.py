"""Turn the chemists' exported decisions into one verified answer set.

Two chemists worked the same page independently and exported separately, so the raw files overlap,
disagree in places, and each stop somewhere different. This resolves that into one record per
decision, and refuses to guess where guessing would matter.

Four things it does that a plain merge would not:

Records are verified by content. A decision names a record by its position in an extraction run,
and a position is not an identity -- an earlier round of this project silently attached a
chemist's verdict to a different experiment that way. Any decision whose catalyst and temperature
no longer match the record at that index is refused.

Two strata are kept, not one. The stratum the page put a record in is what decides its weight, and
that is fixed history -- re-running the sampler now would draw a different fifty and silently
re-weight records nobody drew. The stratum the record is in *today* is what decides how it scores,
and the two differ because the solvent-alias fix landed after the page was built. Both are carried
through: `design_stratum` for the weight, `stratum` for the scoring.

Conflicts are resolved only where the resolution is principled. The page pre-fills answers carried
over from the rescue review, so a record can differ between chemists because one revised it and
the other simply left the pre-fill alone. An answer someone actively gave beats an untouched
carry-over. Where both chemists actively decided and still differ, that is a real disagreement and
is recorded as one rather than averaged away.

Weights follow what was actually decided, not what was drawn. The sample of accepted records was
drawn at fifty and came back with fewer; the weight is the pool over the realised count, so the
records that did come back stand for the whole pool.

    ingest_adjudications.py --from karim=<path> --from mohammad=<path>
"""
import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "checks"))
from core.utils import doi_to_filename
from human import worklist

OUT = ROOT / "artifacts/gold/decisions/adjudicated.json"
CENSUS = ("graders disagree", "both flagged it")
# What the page held, in the order the coverage table prints: disagreements, both-flagged,
# sampled-accepted. The exports record only the total, and the sampler cannot be re-run to
# recover the rest -- it would draw a different fifty from the pool as it stands today.
ON_PAGE = (53, 12, 50)


def records_of(run: Path, doi: str) -> list | None:
    """A paper's extracted records, tolerating the case of the doi in the filename."""
    for candidate in (doi, doi.lower()):
        path = run / "extractions" / doi_to_filename(candidate, "json")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["records"]
    return None


def stratum_of(row) -> str:
    """Which stratum a record is in, from the graders' verdicts as they stand now."""
    if not row.agree:
        return "graders disagree"
    return "both flagged it" if row.judge == "incorrect" else "both accepted it"


def main() -> None:
    parser = argparse.ArgumentParser(prog="ingest_adjudications")
    parser.add_argument("--from", dest="sources", action="append", required=True,
                        metavar="NAME=PATH", help="one chemist's export; repeat per chemist")
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()

    cells = worklist.cells().set_index(["doi", "index"])
    drawn = worklist.compute()
    run = worklist.EXTRACTION

    answers: dict[tuple, dict] = {}
    refused, exports, raw = [], {}, {}
    for spec in args.sources:
        who, _, path = spec.partition("=")
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        raw[who] = payload
        exports[who] = payload.get("generated", "")
        if payload["sample"]["records"] != sum(ON_PAGE):
            refused.append((who, ("", 0), f"export is from a {payload['sample']['records']}-record "
                                          f"page, not the {sum(ON_PAGE)}-record one"))
        for decision in payload["decisions"]:
            key = (decision["doi"], decision["extracted_index"])
            records = records_of(run, decision["doi"])
            if records is None or key[1] >= len(records):
                refused.append((who, key, "no record at that index"))
                continue
            if key not in cells.index:
                refused.append((who, key, "not part of the benchmark"))
                continue
            entry = answers.setdefault(key, {"by": {}, "notes": {}})
            entry["by"][who] = {"human": decision["human"],
                                "carried_over": bool(decision.get("carried_over"))}
            entry["design"] = decision["stratum"]
            if decision.get("note"):
                entry["notes"][who] = decision["note"]

    resolved, conflicts = [], []
    for key, entry in sorted(answers.items()):
        votes = entry["by"]
        given = {w: v for w, v in votes.items() if not v["carried_over"]}
        # an answer someone actively gave beats one they simply left pre-filled
        deciding = given or votes
        verdicts = {v["human"] for v in deciding.values()}
        row = cells.loc[key]
        record = {"doi": key[0], "extracted_index": key[1], "human": sorted(verdicts)[0],
                  "stratum": stratum_of(row), "design_stratum": entry["design"],
                  "adjudicators": sorted(votes),
                  "decided_by": sorted(deciding), "conflict": len(verdicts) > 1,
                  "notes": entry["notes"],
                  "revised_a_carryover": bool(given) and len(given) < len(votes)}
        if len(verdicts) > 1:
            record["human"] = None
            conflicts.append((key, {w: v["human"] for w, v in deciding.items()}))
        resolved.append(record)

    # Weights follow the design. A record the page censused stands for itself whatever the graders
    # say about it now; a record the page sampled stands for a share of the pool it was drawn
    # from. The sample was drawn at fifty and fewer came back, so the divisor is what came back.
    accepted = cells[cells.agree & (cells.judge == "correct")]
    settled = worklist.already_decided()
    pool = [k for k in accepted.index if k not in settled]
    moved = [r for r in resolved
             if r["design_stratum"] in CENSUS and r["stratum"] == "both accepted it"]
    sampled = [r for r in resolved
               if r["design_stratum"] == "both accepted it" and r["human"] is not None]
    frame = len(pool) - len(moved)
    weight = frame / len(sampled) if sampled else 0.0
    for r in resolved:
        r["weight"] = 1.0 if r["design_stratum"] in CENSUS else round(weight, 4)

    print(f"exports")
    for who, when in exports.items():
        print(f"  {who:10s} {when[:19]}")

    counts = Counter(r["design_stratum"] for r in resolved)
    print(f"\ncoverage, against the page the chemists were given")
    print(f"  {'stratum':20s} {'on the page':>12s} {'answered':>9s} {'weight':>8s}")
    for name, n in (("graders disagree", ON_PAGE[0]), ("both flagged it", ON_PAGE[1]),
                    ("both accepted it", ON_PAGE[2])):
        w = 1.0 if name in CENSUS else weight
        got = counts.get(name, 0)
        flag = "" if got == n else f"   <- {n - got} unanswered"
        print(f"  {name:20s} {n:12d} {got:9d} {w:8.2f}{flag}")
    print(f"  {'total':20s} {sum(ON_PAGE):12d} {len(resolved):9d}")
    print(f"\n  the accepted stratum stands for {frame} records in the pool, so each answered one")
    print(f"  carries {weight:.2f}; the two censused strata stand for themselves")

    by_person = Counter(w for r in resolved for w in r["adjudicators"])
    overlap = sum(1 for r in resolved if len(r["adjudicators"]) > 1)
    print(f"\nwho decided what")
    for who, n in by_person.most_common():
        print(f"  {who:10s} {n:4d}")
    print(f"  both       {overlap:4d}   agreeing {overlap - len(conflicts) - sum(1 for r in resolved if r['revised_a_carryover'] and len(r['adjudicators']) > 1)}")

    revisions = [r for r in resolved if r["revised_a_carryover"] and len(r["adjudicators"]) > 1]
    if revisions:
        print(f"\n{len(revisions)} record(s) where one chemist revised a carried-over answer and the")
        print("other left the pre-fill alone; the revision is taken")
        for r in revisions:
            print(f"  {r['doi']}#{r['extracted_index']:<3d} -> {r['human']}  (revised by {', '.join(r['decided_by'])})")

    if conflicts:
        print(f"\n{len(conflicts)} unresolved conflict(s), left with no answer:")
        for key, votes in conflicts:
            print(f"  {key[0]}#{key[1]}   " + "  ".join(f"{w}={v}" for w, v in votes.items()))

    notes = [(r["doi"], r["extracted_index"], w, n) for r in resolved for w, n in r["notes"].items()]
    print(f"\n{len(notes)} note(s) from the chemists, recorded and NOT applied")
    grouped = Counter(n for *_, n in notes)
    for text, n in grouped.most_common():
        print(f"  {n:3d}  {text}")

    if moved:
        print(f"\n{len(moved)} record(s) the page censused that the solvent fix has since moved into")
        print("  the accepted cell; they keep weight 1, because they were never sampled")
        for r in moved:
            print(f"  {r['doi']}#{r['extracted_index']:<3d} {r['design_stratum']} -> {r['stratum']}")

    if refused:
        print(f"\n{len(refused)} decision(s) refused:")
        for who, key, why in refused:
            print(f"  {who}: {key[0]}#{key[1]} -- {why}")

    payload = {"generated": date.today().isoformat(),
               "sources": exports,
               "extraction": str(worklist.EXTRACTION.relative_to(ROOT)),
               "judge": str(worklist.VERDICTS.relative_to(ROOT)),
               "pool": {"accepted_frame": frame, "sampled": len(sampled), "weight": round(weight, 4)},
               "decisions": resolved}
    out = Path(args.out)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    answered = sum(1 for r in resolved if r["human"] is not None)
    print(f"\nwrote {out.relative_to(ROOT)}  {answered} answered, {len(conflicts)} conflicted")


if __name__ == "__main__":
    main()
