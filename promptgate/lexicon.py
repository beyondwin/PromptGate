from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from .config import PromptGateConfig


@dataclass(frozen=True)
class LexiconEntry:
    phrase: str
    interpretation: str
    output_preference: str | None = None
    exclusion: str | None = None


@dataclass(frozen=True)
class LexiconMatch:
    phrase: str
    interpretation: str
    output_preference: str | None
    exclusion: str | None

    def as_prompt_payload(self) -> dict[str, str | None]:
        return {
            "phrase": self.phrase,
            "interpretation": self.interpretation,
            "output_preference": self.output_preference,
            "exclusion": self.exclusion,
        }


def load_lexicon(path: Path) -> list[LexiconEntry]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    if not isinstance(payload, dict) or not isinstance(payload.get("lexicon"), list):
        raise ValueError(f"{path}: expected top-level lexicon list")

    entries: list[LexiconEntry] = []
    for index, item in enumerate(payload["lexicon"]):
        if not isinstance(item, dict):
            raise ValueError(f"{path}: lexicon[{index}] must be a mapping")
        phrase = item.get("phrase")
        interpretation = item.get("interpretation")
        if not isinstance(phrase, str) or not phrase.strip():
            raise ValueError(f"{path}: lexicon[{index}].phrase must be a non-empty string")
        if not isinstance(interpretation, str) or not interpretation.strip():
            raise ValueError(f"{path}: lexicon[{index}].interpretation must be a non-empty string")
        entries.append(
            LexiconEntry(
                phrase=phrase,
                interpretation=interpretation,
                output_preference=_optional_str(item.get("output_preference")),
                exclusion=_optional_str(item.get("exclusion")),
            )
        )
    return entries


def load_configured_lexicon(config: PromptGateConfig) -> list[LexiconEntry]:
    if not config.use_default_korean_lexicon and config.project_lexicon_path is None:
        return []
    if config.project_lexicon_path is None:
        return []
    if not config.project_lexicon_path.exists():
        return []
    return load_lexicon(config.project_lexicon_path)


def match_lexicon(raw_prompt: str, entries: Iterable[LexiconEntry]) -> list[LexiconMatch]:
    matches: list[LexiconMatch] = []
    for entry in entries:
        if entry.phrase in raw_prompt:
            matches.append(
                LexiconMatch(
                    phrase=entry.phrase,
                    interpretation=entry.interpretation,
                    output_preference=entry.output_preference,
                    exclusion=entry.exclusion,
                )
            )
    return matches


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional lexicon fields must be strings when present")
    return value
