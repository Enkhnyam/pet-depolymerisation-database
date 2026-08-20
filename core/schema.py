from __future__ import annotations

import json
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


def load_curated(path: str | Path) -> dict[str, list[Experiment]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    curated: dict[str, list[Experiment]] = {}
    for paper in data:
        curated[paper["doi"]] = [
            Experiment.model_validate(exp["experiment_data"])
            for exp in paper["extracted_experiments"]
        ]
    return curated
