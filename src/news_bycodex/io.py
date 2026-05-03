import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def to_jsonable(item: BaseModel | dict) -> dict:
    if isinstance(item, BaseModel):
        return item.model_dump(mode="json")
    return item


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
