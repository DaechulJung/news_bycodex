from pathlib import Path
from typing import Any

import yaml

from news_bycodex.models import SourceConfig


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return data


def load_sources(path: str | Path) -> list[SourceConfig]:
    data = _load_yaml(Path(path))
    return [SourceConfig.model_validate(item) for item in data.get("sources", []) if item]


def load_keywords(path: str | Path) -> list[str]:
    data = _load_yaml(Path(path))
    keywords = data.get("keywords", [])
    if not isinstance(keywords, list):
        raise ValueError("keywords must be a list")
    return [str(keyword).strip() for keyword in keywords if str(keyword).strip()]
