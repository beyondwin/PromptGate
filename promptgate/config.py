from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .resources import runtime_root


VALID_MODES = {"auto", "suggest", "debug", "off"}
DEFAULT_RISK_POLICY = {
    "low": "auto",
    "medium": "auto",
    "high": "suggest",
    "destructive": "require_confirmation",
}


class ConfigError(ValueError):
    """Raised when PromptGate configuration is invalid."""


@dataclass(frozen=True)
class PromptGateConfig:
    mode: str
    auto_handoff_threshold: float
    max_recommendations: int
    registry_path: Path
    risk_policy: dict[str, str]
    show_refined_prompt: bool
    show_handoff_notice: bool
    debug_on_keyword: bool
    use_default_korean_lexicon: bool
    project_lexicon_path: Path | None

    @classmethod
    def from_mapping(cls, data: dict[str, Any], project_root: Path) -> "PromptGateConfig":
        mode = data.get("mode", "auto")
        if mode not in VALID_MODES:
            raise ConfigError(f"invalid mode {mode!r}; expected one of {sorted(VALID_MODES)}")

        threshold = float(data.get("auto_handoff_threshold", 0.78))
        if not 0 <= threshold <= 1:
            raise ConfigError("auto_handoff_threshold must be between 0 and 1")

        max_recommendations = int(data.get("max_recommendations", 3))
        if max_recommendations < 1:
            raise ConfigError("max_recommendations must be at least 1")

        registry_config = data.get("skill_registry", {})
        registry_path = Path(registry_config.get("registry_path", "./core/skill-registry/examples.yaml"))
        if not registry_path.is_absolute():
            registry_path = project_root / registry_path

        risk_policy = dict(DEFAULT_RISK_POLICY)
        risk_policy.update(data.get("risk_policy", {}))

        output = data.get("output", {})
        lexicon = data.get("lexicon", {})
        lexicon_path_value = lexicon.get("project_lexicon_path")
        lexicon_path = Path(lexicon_path_value) if lexicon_path_value else None
        if lexicon_path is not None and not lexicon_path.is_absolute():
            lexicon_path = project_root / lexicon_path

        return cls(
            mode=mode,
            auto_handoff_threshold=threshold,
            max_recommendations=max_recommendations,
            registry_path=registry_path,
            risk_policy=risk_policy,
            show_refined_prompt=bool(output.get("show_refined_prompt", False)),
            show_handoff_notice=bool(output.get("show_handoff_notice", False)),
            debug_on_keyword=bool(output.get("debug_on_keyword", True)),
            use_default_korean_lexicon=bool(lexicon.get("use_default_korean_lexicon", True)),
            project_lexicon_path=lexicon_path,
        )


def load_config(project_root: Path | None = None) -> PromptGateConfig:
    requested_root = project_root or Path.cwd()
    root = runtime_root(requested_root)
    local_config = requested_root / "promptgate.config.yaml"
    root_local_config = root / "promptgate.config.yaml"
    example_config = root / "promptgate.config.example.yaml"

    if local_config.exists():
        path = local_config
        config_root = requested_root
    elif root_local_config.exists():
        path = root_local_config
        config_root = root
    else:
        path = example_config
        config_root = root

    if not path.exists():
        raise ConfigError(f"PromptGate config not found at {local_config} or {example_config}")

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    if not isinstance(payload, dict) or not isinstance(payload.get("promptgate"), dict):
        raise ConfigError(f"{path}: expected top-level promptgate mapping")

    return PromptGateConfig.from_mapping(payload["promptgate"], project_root=config_root)
