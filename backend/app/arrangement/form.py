from __future__ import annotations

from dataclasses import dataclass

from app.arrangement.profiles import GenreProfile, SectionTemplate, canonical_role

MAX_BARS = 128


@dataclass(frozen=True)
class ArrangementSection:
    id: str
    role: str
    start_bar: int
    bars: int
    energy_start: float
    energy_end: float
    harmony_density: float

    @property
    def end_bar(self) -> int:
        return self.start_bar + self.bars

    @property
    def canonical_role(self) -> str:
        return canonical_role(self.role)

    def energy_at(self, bar: int) -> float:
        """Linear energy interpolation across the section."""
        if self.bars <= 1:
            return self.energy_end
        position = (bar - self.start_bar) / (self.bars - 1)
        position = max(0.0, min(1.0, position))
        return self.energy_start + (self.energy_end - self.energy_start) * position

    def payload(self) -> dict[str, object]:
        return {
            "id": self.id,
            "role": self.role,
            "canonical_role": self.canonical_role,
            "start_bar": self.start_bar,
            "bars": self.bars,
            "energy_start": self.energy_start,
            "energy_end": self.energy_end,
            "harmony_density": self.harmony_density,
        }


def build_form(
    profile: GenreProfile,
    total_bars: int | None,
    custom_sections: list[SectionTemplate] | None,
    energy: float,
    section_contrast: float,
) -> list[ArrangementSection]:
    """Produce named sections with exact bar ranges filling the total bar count."""
    if custom_sections:
        sections = _from_templates(custom_sections, energy, section_contrast)
        if total_bars is not None and sections[-1].end_bar != total_bars:
            raise ValueError(
                f"custom form spans {sections[-1].end_bar} bars but the clock declares "
                f"{total_bars} bars; they must match"
            )
        return sections
    bars = total_bars if total_bars is not None else sum(s.bars for s in profile.default_form)
    if not 1 <= bars <= MAX_BARS:
        raise ValueError(f"total bars must be between 1 and {MAX_BARS}")
    return _tile_template(profile.default_form, bars, energy, section_contrast)


def _from_templates(
    templates: list[SectionTemplate], energy: float, section_contrast: float
) -> list[ArrangementSection]:
    sections: list[ArrangementSection] = []
    start = 0
    for index, template in enumerate(templates):
        energy_start, energy_end = _apply_macros(
            template.energy_start, template.energy_end, energy, section_contrast
        )
        sections.append(
            ArrangementSection(
                id=f"sec-{index + 1}",
                role=template.role,
                start_bar=start,
                bars=template.bars,
                energy_start=energy_start,
                energy_end=energy_end,
                harmony_density=template.harmony_density,
            )
        )
        start += template.bars
    if sections[-1].end_bar > MAX_BARS:
        raise ValueError(f"the form exceeds the {MAX_BARS} bar limit")
    return sections


def _tile_template(
    template: list[SectionTemplate], total_bars: int, energy: float, section_contrast: float
) -> list[ArrangementSection]:
    sections: list[ArrangementSection] = []
    start = 0
    index = 0
    while start < total_bars:
        section_template = template[index % len(template)]
        bars = min(section_template.bars, total_bars - start)
        energy_start, energy_end = _apply_macros(
            section_template.energy_start, section_template.energy_end, energy, section_contrast
        )
        sections.append(
            ArrangementSection(
                id=f"sec-{index + 1}",
                role=section_template.role,
                start_bar=start,
                bars=bars,
                energy_start=energy_start,
                energy_end=energy_end,
                harmony_density=section_template.harmony_density,
            )
        )
        start += bars
        index += 1
    return sections


def _apply_macros(
    energy_start: float, energy_end: float, energy: float, section_contrast: float
) -> tuple[float, float]:
    """Energy macro pulls levels toward the global energy; contrast scales the spread."""
    mean = (energy_start + energy_end) / 2
    shifted = mean + (energy - 0.5) * 0.6
    half_spread = (energy_end - energy_start) / 2 * (0.25 + section_contrast)
    low = max(0.0, min(1.0, shifted - half_spread))
    high = max(0.0, min(1.0, shifted + half_spread))
    return round(low, 4), round(high, 4)
