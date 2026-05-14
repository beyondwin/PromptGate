from __future__ import annotations

from pathlib import Path


def source_root() -> Path:
    return Path(__file__).resolve().parents[1]


def package_asset_root() -> Path:
    return Path(__file__).resolve().parent / "assets"


def runtime_root(project_root: Path | None = None) -> Path:
    candidate = (project_root or Path.cwd()).resolve()
    if _looks_like_promptgate_root(candidate):
        return candidate
    assets = package_asset_root()
    if _looks_like_promptgate_root(assets):
        return assets
    return candidate


def _looks_like_promptgate_root(path: Path) -> bool:
    return (
        (path / "promptgate.config.yaml").is_file()
        or (path / "promptgate.config.example.yaml").is_file()
    ) and (path / "core/output-contract/promptgate-result.schema.json").is_file()
