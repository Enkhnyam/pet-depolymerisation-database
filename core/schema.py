from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, create_model


class Experiment(BaseModel):
    # populate_by_name lets us build from either the field name or the alias;
    # extra="ignore" drops keys we don't model (e.g. experiment_number).
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    catalyst: str | None = Field(None, description="Catalyst name exactly as written")
    solvent: str | None = Field(None, description="Solvent name exactly as written")
    temperature_c: float | None = Field(None, description="Temperature in Celsius")
    reaction_time_min: float | None = Field(None, description="Reaction time in minutes")
    catalyst_amount_g: float | None = Field(None, description="Catalyst amount in grams")
    pet_amount_g: float | None = Field(None, alias="PET_amount_g", description="PET amount in grams")
    solvent_amount_g: float | None = Field(None, description="Solvent amount in grams")
    yield_percent: float | None = Field(None, description="Yield %")
    selectivity_percent: float | None = Field(None, description="Selectivity %")
    conversion_percent: float | None = Field(None, description="Conversion %")
    pressure_atm: float | None = Field(None, description="Pressure in atm, only if stated")
    source_chunk_ids: list[str] = Field(
        default_factory=list,
        description="UUIDs (ID: tags) of the chunks these values came from",
    )


class ExtractionResponse(BaseModel):
    experiments: list[Experiment] = Field(default_factory=list)


# Experiment minus provenance — the OFF arm of the source-tracking ablation. Built from Experiment
# so the two arms can never drift apart. Turning source tracking off needs all three: the prompt
# section removed, source_chunk_ids stripped from the few-shot demos (`drop_source_chunks` in
# harness_params), and the field absent from the response schema — this model.
ExperimentNoSource = create_model(
    "ExperimentNoSource",
    __config__=Experiment.model_config,
    **{name: (f.annotation, f) for name, f in Experiment.model_fields.items()
       if name != "source_chunk_ids"},
)


class ExtractionResponseNoSource(BaseModel):
    experiments: list[ExperimentNoSource] = Field(default_factory=list)


# doi -> the schema's own spelling of a field. The judge names PET_amount_g both ways -- 255
# corrections under the alias and 23 under "pet_amount_g" -- and a case-sensitive lookup silently
# discarded the latter, so a correction the judge made was dropped without being counted anywhere.
_BY_LOWER = {}


def canonical_field(name: str) -> str | None:
    """The schema field a judge's field name refers to, or None if it names nothing we store."""
    if not _BY_LOWER:
        for field, info in Experiment.model_fields.items():
            spelling = info.alias or field
            _BY_LOWER[field.lower()] = spelling
            _BY_LOWER[spelling.lower()] = spelling
    return _BY_LOWER.get(str(name).strip().lower())


# Papers name one solvent two ways -- "ethylene glycol" in the prose, "EG" in the table header --
# and the model copies whichever it read. Every solvent disagreement in the whole benchmark, all
# 54 of them, is that one substance under two spellings; not one is a genuinely different
# solvent. Comparing the raw strings therefore measured spelling, and spent a tenth of the accept
# budget on it. Only unambiguous single-substance aliases belong here: mixtures like "KF:EG 1:6"
# or "methanol/GVL" are left exactly as written, because deciding what those are is chemistry.
_SOLVENT_ALIASES = {
    "eg": "ethylene glycol",
    "deg": "diethylene glycol",
    "peg": "polyethylene glycol",
    "bdo": "1,4-butanediol",
    "dpg": "dipropylene glycol",
    "npg": "neopentyl glycol",
    "h2o": "water",
    "distilled water": "water",
    "deionized water": "water",
    "deionised water": "water",
    "di water": "water",
    "meoh": "methanol",
    "etoh": "ethanol",
    "iproh": "isopropanol",
    "2-propanol": "isopropanol",
    "thf": "tetrahydrofuran",
    "dmso": "dimethyl sulfoxide",
    "dmf": "dimethylformamide",
}


def canonical_solvent(name) -> str:
    """A solvent name reduced to one spelling, so a comparison tests the substance."""
    text = " ".join(str(name or "").split()).lower()
    return _SOLVENT_ALIASES.get(text, text)


# The route is not extracted; it is read off the solvent, because the solvent is what decides it.
# These three patterns were written out twice, byte-identical, in checks/database/chemistry.py
# and checks/release/release_numbers.py -- two files that report route counts for two different
# populations and would have silently disagreed the moment either was edited.
ROUTE_FROM_SOLVENT = [
    ("glycolysis", r"ethylene glycol|\beg\b|glycol(?!ic)|diethylene|propylene glycol"),
    ("methanolysis", r"methanol|\bmeoh\b"),
    ("hydrolysis", r"water|aqueous|\bnaoh\b|\bkoh\b|h2so4|h3po4|acid solution|steam"),
]
OTHER_ROUTE = "other/unclear"
# The three routes the schema covers, in the order this literature lists them. The names are
# chemistry and belong here; their colours are presentation and stay in figures/_style.py.
ROUTES = ["glycolysis", "hydrolysis", "methanolysis"]


def route_of(solvent) -> str:
    """Which depolymerisation route a solvent name implies.

    Matched in order, so a mixed solvent takes the first rule that fires; release quality
    reports how many rows that affects rather than hiding it.

    ponytail: matches the raw string, not canonical_solvent(). Routing the canonical name
    instead would recover about 150 rows now filed as other/unclear purely because the paper
    wrote DEG, MEG, TEG or CH3OH -- but it moves published route counts, so it is a decision for
    whoever owns the numbers, not a refactor.
    """
    text = str(solvent or "").lower()
    for route, pattern in ROUTE_FROM_SOLVENT:
        if re.search(pattern, text):
            return route
    return OTHER_ROUTE


def load_curated(path: str | Path) -> dict[str, list[Experiment]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    curated: dict[str, list[Experiment]] = {}
    for paper in data:
        curated[paper["doi"]] = [
            Experiment.model_validate(exp["experiment_data"])
            for exp in paper["extracted_experiments"]
        ]
    return curated
