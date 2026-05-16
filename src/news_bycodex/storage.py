from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from news_bycodex.analysis import canonical_url
from news_bycodex.io import ensure_dir
from news_bycodex.models import RawItem


class SeenItemStore:
    def __init__(self, path: str | Path = "data/state/seen_items.sqlite") -> None:
        self.path = Path(path)
        ensure_dir(self.path.parent)
        self._initialize()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_items (
                    url_key TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL
                )
                """
            )

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def filter_unseen(self, items: list[RawItem]) -> list[RawItem]:
        if not items:
            return []
        with self.connect() as connection:
            seen = {
                row[0]
                for row in connection.execute(
                    "SELECT url_key FROM seen_items WHERE url_key IN ({})".format(
                        ",".join("?" for _ in items)
                    ),
                    [canonical_url(item.url) for item in items],
                )
            }
        return [item for item in items if canonical_url(item.url) not in seen]

    def mark_seen(self, items: list[RawItem]) -> None:
        if not items:
            return
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (canonical_url(item.url), item.url, item.title, item.source_id, now)
            for item in items
        ]
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO seen_items
                (url_key, url, title, source_id, first_seen_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )

    def bootstrap_from_processed(
        self,
        processed_root: str | Path = "data/processed",
        *,
        exclude_date: str | None = None,
    ) -> None:
        root = Path(processed_root)
        if not root.exists():
            return
        rows = []
        now = datetime.now(timezone.utc).isoformat()
        for trends_path in root.glob("*/trends.jsonl"):
            if exclude_date and trends_path.parent.name == exclude_date:
                continue
            for line in trends_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                url = str(item.get("url") or "").strip()
                title = str(item.get("title") or "").strip()
                source = str(item.get("source") or "processed").strip()
                if not url or not title:
                    continue
                rows.append((canonical_url(url), url, title, source, now))
        if not rows:
            return
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO seen_items
                (url_key, url, title, source_id, first_seen_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )
