from collections import OrderedDict

from news_bycodex.models import Impact, Maturity, RawItem, TrendItem


def dedupe_raw_items(items: list[RawItem]) -> list[RawItem]:
    deduped: OrderedDict[str, RawItem] = OrderedDict()
    for item in items:
        key = item.url.rstrip("/").lower()
        if key not in deduped:
            deduped[key] = item
    return list(deduped.values())


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
    if "prototype" in lowered or "demo" in lowered:
        return "prototype"
    if "beta" in lowered or "preview" in lowered:
        return "beta"
    if "adopted" in lowered or "production" in lowered:
        return "adopted"
    return "released"


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
    if raw.metadata.get("stars", 0) >= 100:
        score += 1
    if raw.title.lower() in history_text.lower():
        score -= 1
    return max(1, min(5, score))


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
