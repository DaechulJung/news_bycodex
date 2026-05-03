from pathlib import Path
from typing import Any, Mapping

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
    sources = data.get("sources")
    if not isinstance(sources, list):
        raise ValueError("sources must be a list")

    configs: list[SourceConfig] = []
    for index, item in enumerate(sources):
        if not isinstance(item, Mapping):
            raise ValueError(f"sources[{index}] must be a mapping")
        configs.append(SourceConfig.model_validate(item))
    return configs


def load_keywords(path: str | Path) -> list[str]:
    data = _load_yaml(Path(path))
    keywords = data.get("keywords", [])
    if not isinstance(keywords, list):
        raise ValueError("keywords must be a list")
    return [str(keyword).strip() for keyword in keywords if str(keyword).strip()]
