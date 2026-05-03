from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


SourceType = Literal["rss", "hn_algolia", "arxiv", "github_search", "reddit_json", "web"]
Category = Literal[
    "model",
    "agent_framework",
    "coding_agent",
    "research",
    "product",
    "tooling",
    "benchmark",
    "company",
    "other",
]
Maturity = Literal["rumor", "prototype", "beta", "released", "adopted"]
Impact = Literal["low", "medium", "high", "strategic"]


class SourceConfig(BaseModel):
    id: str
    name: str
    type: SourceType
    enabled: bool = True
    url: HttpUrl | None = None
    credibility: float = Field(default=0.5, ge=0.0, le=1.0)
    limit: int = Field(default=10, ge=1, le=100)
    selectors: dict[str, str] = Field(default_factory=dict)


class RawItem(BaseModel):
    source_id: str
    source_name: str
    source_type: SourceType
    title: str
    url: str
    published_at: datetime | None = None
    summary: str = ""
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrendItem(BaseModel):
    title: str
    url: str
    source: str
    published_at: datetime | None = None
    summary: str
    category: Category
    maturity: Maturity
    impact: Impact
    signal_strength: int = Field(ge=1, le=5)
    why_it_matters: str
    related_items: list[str] = Field(default_factory=list)


class ReportData(BaseModel):
    date: str
    generated_at: datetime
    executive_summary: str
    top_trends: list[TrendItem]
    weak_signals: list[TrendItem]
    deferred_items: list[TrendItem]
    source_errors: list[dict[str, str]] = Field(default_factory=list)
