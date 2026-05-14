from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import re

import yaml


RISK_LEVELS = {"low", "medium", "high", "destructive"}
SKILL_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]*$")


class RegistryError(ValueError):
    """Raised when a skill registry is invalid."""


@dataclass(frozen=True)
class Skill:
    id: str
    description: str
    aliases: list[str]
    domains: list[str]
    task_types: list[str]
    trigger_phrases: list[str]
    risk_level: str
    auto_invocable: bool
    platform_names: dict[str, str | None]

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Skill":
        skill_id = data.get("id")
        if not isinstance(skill_id, str) or not SKILL_ID_PATTERN.match(skill_id):
            raise RegistryError(f"invalid skill id {skill_id!r}")

        risk_level = data.get("risk_level")
        if risk_level not in RISK_LEVELS:
            raise RegistryError(f"invalid risk_level {risk_level!r} for {skill_id!r}")

        auto_invocable = data.get("auto_invocable")
        if not isinstance(auto_invocable, bool):
            raise RegistryError(f"auto_invocable must be boolean for {skill_id!r}")

        return cls(
            id=skill_id,
            description=_required_string(data, "description", skill_id),
            aliases=_string_list(data, "aliases", skill_id),
            domains=_string_list(data, "domains", skill_id),
            task_types=_string_list(data, "task_types", skill_id),
            trigger_phrases=_string_list(data, "trigger_phrases", skill_id),
            risk_level=risk_level,
            auto_invocable=auto_invocable,
            platform_names=dict(data.get("platform_names", {})),
        )

    def as_prompt_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "aliases": self.aliases,
            "domains": self.domains,
            "task_types": self.task_types,
            "trigger_phrases": self.trigger_phrases,
            "risk_level": self.risk_level,
            "auto_invocable": self.auto_invocable,
        }


class SkillRegistry:
    def __init__(self, skills: list[Skill]):
        self._skills = list(skills)
        self._by_id = {skill.id: skill for skill in skills}
        if len(self._by_id) != len(skills):
            raise RegistryError("duplicate skill id in registry")

    @classmethod
    def from_records(cls, records: list[dict[str, Any]]) -> "SkillRegistry":
        return cls([Skill.from_mapping(record) for record in records])

    def has(self, skill_id: str) -> bool:
        return skill_id in self._by_id

    def get(self, skill_id: str) -> Skill:
        try:
            return self._by_id[skill_id]
        except KeyError as exc:
            raise RegistryError(f"unknown skill {skill_id!r}") from exc

    def as_prompt_payload(self) -> list[dict[str, Any]]:
        return [skill.as_prompt_payload() for skill in self._skills]


def load_registry(path: Path) -> SkillRegistry:
    if not path.exists():
        raise RegistryError(f"registry file does not exist: {path}")

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    if not isinstance(payload, dict) or not isinstance(payload.get("skills"), list):
        raise RegistryError(f"{path}: expected skills list")

    return SkillRegistry.from_records(payload["skills"])


def _required_string(data: dict[str, Any], field: str, skill_id: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value:
        raise RegistryError(f"{field} must be a non-empty string for {skill_id!r}")
    return value


def _string_list(data: dict[str, Any], field: str, skill_id: str) -> list[str]:
    value = data.get(field)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RegistryError(f"{field} must be a list of strings for {skill_id!r}")
    return value
