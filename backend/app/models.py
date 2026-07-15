from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CPSRequest(BaseModel):
    factors: list[int] = Field(min_length=1, max_length=16)
    choose: int = Field(ge=1, le=16)
    kind: Literal["harmonic", "subharmonic"] = "harmonic"
    octave_reduce: bool = True

    @field_validator("factors")
    @classmethod
    def factors_must_be_positive(cls, values: list[int]) -> list[int]:
        if any(value < 1 for value in values):
            raise ValueError("factors must contain positive integers")
        if len(set(values)) != len(values):
            raise ValueError("factors must be unique")
        return values


class EulerFokkerRequest(BaseModel):
    factors: list[int] = Field(min_length=1, max_length=12)
    octave_reduce: bool = True

    @field_validator("factors")
    @classmethod
    def factors_must_be_greater_than_one(cls, values: list[int]) -> list[int]:
        if any(value < 2 for value in values):
            raise ValueError("Euler–Fokker factors must be integers greater than one")
        return values


class SeriesRequest(BaseModel):
    count: int = Field(ge=1, le=128)
    octave_reduce: bool = True


class RatioRequest(BaseModel):
    ratio: str = Field(pattern=r"^\d+/\d+$")


class ScalaRequest(BaseModel):
    name: str = Field(default="Pure Intonation Scale", min_length=1, max_length=80)
    ratios: list[str] = Field(min_length=1, max_length=256)


class HarmonicGraphRequest(BaseModel):
    factors: list[int] = Field(min_length=2, max_length=16)
    choose: int = Field(ge=1, le=16)
    operation: Literal["graph", "shortest_path", "random_walk", "weighted_walk"] = "graph"
    start: int = Field(default=0, ge=0)
    end: int | None = Field(default=None, ge=0)
    steps: int = Field(default=8, ge=0, le=10_000)
    seed: int = 0
    metric: Literal["harmonic", "monzo", "cent"] = "harmonic"

    @field_validator("factors")
    @classmethod
    def graph_factors_must_be_positive_and_unique(cls, values: list[int]) -> list[int]:
        if any(value < 1 for value in values):
            raise ValueError("factors must contain positive integers")
        if len(set(values)) != len(values):
            raise ValueError("factors must be unique")
        return values


class HarmonyRequest(BaseModel):
    factors: list[int] = Field(min_length=2, max_length=16)
    choose: int = Field(ge=1, le=16)
    length: int = Field(default=8, ge=1, le=10_000)
    start: int = Field(default=0, ge=0)
    seed: int = 0
    metric: Literal["harmonic", "monzo", "cent"] = "harmonic"

    @field_validator("factors")
    @classmethod
    def harmony_factors_must_be_positive_and_unique(cls, values: list[int]) -> list[int]:
        if any(value < 1 for value in values):
            raise ValueError("factors must contain positive integers")
        if len(set(values)) != len(values):
            raise ValueError("factors must be unique")
        return values
