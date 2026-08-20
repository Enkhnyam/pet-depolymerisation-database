"""The headline. Every other metric check explains a number on this page."""
from _setup import *

result = totals()
print(f"\nrun {EXTRACTION.name}")
show("scores", {"experiments in table": len(curated()),
                "records extracted": len(records()),
                "precision": result["precision"],
                "recall": result["recall"],
                "f1": result["f1"],
                "correct": result["tp"],
                "false alarms": result["fp"],
                "missed": result["fn"]})
