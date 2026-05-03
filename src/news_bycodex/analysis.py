from collections import OrderedDict
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from news_bycodex.models import Impact, Maturity, RawItem, TrendItem


SOURCE_QUALITY = {
    "github_search": 5,
    "arxiv": 5,
    "hn_algolia": 4,
    "rss": 3,
    "reddit_json": 2,
    "web": 1,
}


def canonical_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = "https"
    netloc = parsed.netloc.lower()
    path = canonical_path(netloc, parsed.path)
    query = canonical_query(parsed.query)
    return urlunparse((scheme, netloc, path, "", query, ""))


def canonical_path(netloc: str, path: str) -> str:
    normalized_path = path.rstrip("/") or "/"
    if netloc == "arxiv.org" and normalized_path.startswith("/pdf/"):
        paper_id = normalized_path.removeprefix("/pdf/").removesuffix(".pdf")
        return f"/abs/{paper_id}"
    return normalized_path


def canonical_query(query: str) -> str:
    params = [
        (key, value)
        for key, value in parse_qsl(query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
    ]
    return urlencode(sorted(params))


def dedupe_raw_items(items: list[RawItem]) -> list[RawItem]:
    groups: OrderedDict[str, list[tuple[int, RawItem]]] = OrderedDict()
    exact_keys: dict[str, set[str]] = {}
    for item in items:
        key = canonical_url(item.url)
        groups.setdefault(key, []).append((len(groups.get(key, [])), item))
        exact_keys.setdefault(key, set()).add(exact_url(item.url))

    deduped = []
    for key, group in groups.items():
        if len(group) == 1 or len(exact_keys[key]) == 1:
            representative = group[0][1]
        else:
            representative = max(group, key=representative_quality)[1]
        deduped.append(with_duplicate_evidence(representative, [item for _, item in group]))
    return deduped


def exact_url(url: str) -> str:
    return url.rstrip("/").lower()


def representative_quality(indexed_item: tuple[int, RawItem]) -> tuple[int, int, int]:
    index, item = indexed_item
    return (
        SOURCE_QUALITY.get(item.source_type, 0),
        richness_score(item),
        -index,
    )


def richness_score(item: RawItem) -> int:
    return len(item.summary) + len(item.metadata)


def with_duplicate_evidence(representative: RawItem, duplicates: list[RawItem]) -> RawItem:
    metadata = dict(representative.metadata)
    metadata["duplicate_count"] = len(duplicates)
    metadata["duplicate_sources"] = list(dict.fromkeys(item.source_id for item in duplicates))
    return representative.model_copy(update={"metadata": metadata})


def classify_category(text: str) -> str:
    lowered = text.lower()
    if "coding agent" in lowered or "claude code" in lowered or "codex" in lowered:
        return "coding_agent"
    if "agent framework" in lowered or "agentic framework" in lowered:
        return "agent_framework"
    if "benchmark" in lowered or "leaderboard" in lowered:
        return "benchmark"
    if "arxiv" in lowered or "paper" in lowered or "research" in lowered:
        return "research"
    if "model" in lowered or "llm" in lowered:
        return "model"
    if "release" in lowered or "launch" in lowered or "product" in lowered:
        return "product"
    return "other"


def classify_maturity(text: str) -> Maturity:
    lowered = text.lower()
    if "rumor" in lowered or "leak" in lowered:
        return "rumor"
    if "beta" in lowered or "preview" in lowered:
        return "beta"
    if "adopted" in lowered or "production" in lowered:
        return "adopted"
    if any(token in lowered for token in ["release", "launch", "available", "announced"]):
        return "released"
    if any(
        token in lowered
        for token in ["prototype", "demo", "proposes", "research", "paper", "arxiv"]
    ):
        return "prototype"
    return "prototype"


def impact_from_score(score: int) -> Impact:
    if score >= 5:
        return "strategic"
    if score >= 4:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def signal_score(raw: RawItem, source_credibility: float, history_text: str) -> int:
    text = f"{raw.title} {raw.summary}".lower()
    score = 1
    if source_credibility >= 0.8:
        score += 1
    if any(token in text for token in ["agent", "codex", "claude code", "autonomous", "framework"]):
        score += 1
    if any(token in text for token in ["release", "launched", "benchmark", "paper", "github"]):
        score += 1
    if star_count(raw.metadata.get("stars")) >= 100:
        score += 1
    if raw.title.lower() in history_text.lower():
        score -= 1
    return max(1, min(5, score))


def star_count(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def normalize_item(raw: RawItem, source_credibility: float, history_text: str) -> TrendItem:
    text = f"{raw.title} {raw.summary}"
    score = signal_score(raw, source_credibility, history_text)
    category = classify_category(text)
    return TrendItem(
        title=raw.title,
        url=raw.url,
        source=raw.source_name,
        published_at=raw.published_at,
        summary=raw.summary or raw.title,
        category=category,
        maturity=classify_maturity(text),
        impact=impact_from_score(score),
        signal_strength=score,
        why_it_matters=why_it_matters(category, score),
        related_items=[],
    )


def why_it_matters(category: str, score: int) -> str:
    if category == "coding_agent":
        return "This may affect developer workflows and autonomous software engineering adoption."
    if category == "agent_framework":
        return "This may shape how teams build, evaluate, and operate agentic systems."
    if category == "research":
        return "This may introduce techniques that product teams adopt after validation."
    if score >= 4:
        return "This has strong relevance to near-term Agent/AI strategy."
    return "This is a weak signal worth tracking for follow-up."
