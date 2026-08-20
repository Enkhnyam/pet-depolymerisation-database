"""The headline scores. Every other metric check explains a number on this page."""
from _setup import EXTRACTION, curated, records, show, totals


def main() -> None:
    result = totals()

    scores = {
        "experiments in table": len(curated()),
        "records extracted": len(records()),
        "precision": result["precision"],
        "recall": result["recall"],
        "f1": result["f1"],
        "correct": result["tp"],
        "false alarms": result["fp"],
        "missed": result["fn"],
    }

    print(f"\nrun {EXTRACTION.name}")
    show("scores", scores)


if __name__ == "__main__":
    main()
