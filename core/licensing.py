import json

from .paths import resolve


def licensable_dois() -> set[str]:
    entries = json.loads(resolve("licenses.json").read_text(encoding="utf-8"))
    return {entry["doi"] for entry in entries}
