from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def normalize_json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {key: normalize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_json_value(item) for item in value]
    return value


def to_jsonable(item: BaseModel | dict) -> dict:
    if isinstance(item, BaseModel):
        return item.model_dump(mode="json")
    return normalize_json_value(item)


def write_jsonl(path: str | Path, items: Iterable[BaseModel | dict]) -> None:
    output = Path(path)
    ensure_dir(output.parent)
    with output.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(to_jsonable(item), ensure_ascii=False) + "\n")


def append_jsonl(path: str | Path, item: BaseModel | dict) -> None:
    output = Path(path)
    ensure_dir(output.parent)
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(to_jsonable(item), ensure_ascii=False) + "\n")


def write_source_error(path: str | Path, source_id: str, message: str) -> None:
    append_jsonl(
        path,
        {
            "source_id": source_id,
            "message": message,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
    )
