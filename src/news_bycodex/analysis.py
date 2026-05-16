from collections import OrderedDict
import html
import re
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

TOKEN_RE = re.compile(r"[a-z0-9가-힣]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "new",
    "of",
    "on",
    "the",
    "to",
    "with",
}
AGENT_RELATED_CATEGORIES = {"coding_agent", "agent_framework", "harness_engineering"}
IMPACT_RANK = {"low": 1, "medium": 2, "high": 3, "strategic": 4}
HTML_TAG_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"https?://[^\s)]+")
WHITESPACE_RE = re.compile(r"\s+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
LEADING_NOISE_RE = re.compile(
    r"^(hey hn!|hello hn[,!]?|hi everyone[,!]?|hey folks[,!]?)\s*",
    re.IGNORECASE,
)
PERSONAL_LAUNCH_RE = re.compile(
    r"^(my friend and i|we|i)\s+(made and\s+)?(just\s+)?(launched|built|created)\s+",
    re.IGNORECASE,
)
REFERENCE_PARENS_RE = re.compile(r"\s*\([^)]*(example|see|http)[^)]*\)", re.IGNORECASE)
SPEC_HANDOFF_RE = re.compile(
    r"then\s+we\s+put\s+everything\s+together\s+into\s+a\s+comprehensive\s+speq\s+"
    r"that\s+you\s+can\s+then\s+turn\s+into\s+a\s+prd,\s+share\s+with\s+colleagues\s+"
    r"to\s+evaluate\s+and\s+collaborate\s+on,\s+or\s+hand\s+off\s+to\s+an\s+agent\s+"
    r"to\s+build\s+via\s+mcp\.",
    re.IGNORECASE,
)
SUMMARY_PRIORITY_TERMS = (
    "agent",
    "mcp",
    "prd",
    "llm",
    "ai",
    "codex",
    "claude",
    "framework",
    "benchmark",
    "github",
    "model",
)
HOT_RELEASE_TERMS = ("release", "released", "launch", "launched", "announce", "announced")
HOT_MODEL_TERMS = (
    "gpt 5",
    "gpt-5",
    "gpt 5.5",
    "gpt-5.5",
    "opus",
    "grok",
    "claude",
    "codex",
    "openai",
    "anthropic",
    "gemini",
)
HOT_MODEL_PATTERNS = (
    re.compile(r"\bgpt[-\s]?5(?:\.5)?\b", re.IGNORECASE),
    re.compile(r"\bclaude(?:\s+code)?\b", re.IGNORECASE),
    re.compile(r"\bcodex\b", re.IGNORECASE),
    re.compile(r"\bgrok\b", re.IGNORECASE),
    re.compile(r"\bgemini\b", re.IGNORECASE),
    re.compile(r"\bopus\b", re.IGNORECASE),
)
HARNESS_ENGINEERING_TERMS = (
    "agent harness",
    "harness engineering",
    "agent runtime",
    "agent orchestration",
    "subagent",
    "multi-agent",
    "multi agent",
    "tool calling",
    "tool use",
    "durable execution",
    "agent observability",
    "observability",
    "tracing",
    "agent evaluation",
    "eval harness",
    "agent ops",
    "agentops",
    "langgraph",
    "langsmith",
    "llamaindex",
    "llamaparse",
    "model context protocol",
    "mcp server",
    "하네스",
    "에이전틱",
    "도구 호출",
    "관찰성",
    "평가 하네스",
)
TITLE_PREFIX_RE = re.compile(r"^(show hn:|ask hn:|launch hn:)\s*", re.IGNORECASE)
TAG_COLUMNS = (
    "model",
    "openai",
    "anthropic",
    "google",
    "xai",
    "meta",
    "huggingface",
    "coding_agent",
    "agent_framework",
    "harness_engineering",
    "agentic",
    "autonomous_agent",
    "orchestration",
    "subagent",
    "mcp",
    "plugin",
    "memory",
    "benchmark",
    "evaluation",
    "observability",
    "research",
    "release",
    "pricing",
    "api",
    "tool_use",
    "github",
    "youtube",
    "community",
    "paper",
    "open_source",
    "cli",
    "ide",
    "workflow",
    "security",
    "multimodal",
    "image",
    "video",
    "tooling",
)


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


def group_similar_trends(trends: list[TrendItem]) -> list[TrendItem]:
    groups: list[list[TrendItem]] = []
    for trend in trends:
        for group in groups:
            if any(are_similar_trends(existing, trend) for existing in group):
                group.append(trend)
                break
        else:
            groups.append([trend])
    return [merge_trend_group(group) for group in groups]


def are_similar_trends(left: TrendItem, right: TrendItem) -> bool:
    if canonical_url(left.url) == canonical_url(right.url):
        return True
    overlap = token_overlap(title_tokens(left.title), title_tokens(right.title))
    if hot_entities(left.title) & hot_entities(right.title) and overlap >= 0.45:
        return True
    if {left.category, right.category} <= AGENT_RELATED_CATEGORIES:
        return overlap >= 0.6
    return left.category == right.category and overlap >= 0.75


def hot_entities(text: str) -> set[str]:
    return {pattern.pattern for pattern in HOT_MODEL_PATTERNS if pattern.search(text)}


def title_tokens(title: str) -> set[str]:
    return {
        normalize_token(token)
        for token in TOKEN_RE.findall(title.lower())
        if normalize_token(token) not in STOPWORDS
    }


def normalize_token(token: str) -> str:
    if token.startswith("agent"):
        return "agent"
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def token_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def merge_trend_group(group: list[TrendItem]) -> TrendItem:
    if len(group) == 1:
        return group[0]
    representative = max(group, key=trend_rank)
    related_items = list(representative.related_items)
    image = representative.image_url or next((trend.image_url for trend in group if trend.image_url), None)
    for trend in group:
        related_items.append(f"{trend.source}: {trend.url}")
        related_items.extend(trend.related_items)
    return representative.model_copy(
        update={"image_url": image, "related_items": unique_items(related_items)}
    )


def trend_rank(trend: TrendItem) -> tuple[int, int, int]:
    return (
        trend.signal_strength,
        IMPACT_RANK[trend.impact],
        len(trend.summary),
    )


def unique_items(items: list[str]) -> list[str]:
    return list(OrderedDict.fromkeys(items))


def sort_trends_by_hotness(trends: list[TrendItem]) -> list[TrendItem]:
    scored = [
        trend.model_copy(update={"hotness_score": trend_hotness_score(trend)})
        for trend in trends
    ]
    return sorted(
        scored,
        key=lambda trend: (
            trend.hotness_score,
            trend.signal_strength,
            published_sort_key(trend),
            trend.title,
        ),
        reverse=True,
    )


def published_sort_key(trend: TrendItem) -> str:
    if trend.published_at is None:
        return ""
    return trend.published_at.isoformat()


def trend_hotness_score(trend: TrendItem) -> float:
    text = f"{trend.title} {trend.summary}".lower()
    related_count = related_news_count(trend.related_items)
    score = trend.signal_strength * 10
    score += IMPACT_RANK[trend.impact] * 2
    score += min(related_count, 8) * 8
    has_release = any(term in text for term in HOT_RELEASE_TERMS)
    has_hot_model = is_model_release_signal(text) or is_model_focused_signal(text)
    if has_release:
        score += 8
    if has_hot_model:
        score += 12
    if is_harness_engineering_signal(text):
        score += 10
    if has_release and has_hot_model:
        score += 8
    if has_release and is_harness_engineering_signal(text):
        score += 6
    if related_count >= 2:
        score += 10
    if related_count >= 4:
        score += 8
    return float(score)


def related_news_count(related_items: list[str]) -> int:
    urls = OrderedDict()
    for item in related_items:
        if "discussion:" in item.lower():
            continue
        match = re.search(r"https?://[^\s)>,]+", item)
        if match:
            urls[canonical_url(match.group(0).rstrip(".,"))] = True
    return len(urls)


def summarize_for_report(title: str, body: str, max_chars: int = 320) -> str:
    cleaned = clean_report_text(body) or clean_report_text(title)
    cleaned = PERSONAL_LAUNCH_RE.sub("", cleaned).strip()
    if not cleaned:
        return title[:max_chars]

    sentences = [
        sentence.strip()
        for sentence in SENTENCE_SPLIT_RE.split(cleaned)
        if sentence.strip() and not is_summary_noise(sentence)
    ]
    summary = select_summary_sentences(sentences, max_chars) if sentences else cleaned
    return truncate_text(summary, max_chars)


def summarize_korean_for_report(
    title: str,
    body: str,
    category: str,
    max_chars: int = 260,
) -> str:
    clean_title = clean_report_title(title)
    cleaned_body = clean_report_text(body)
    text = f"{clean_title} {cleaned_body}".lower()
    fact_excerpt = news_fact_excerpt(clean_title, cleaned_body)

    if fact_excerpt:
        return truncate_text(f"{clean_title}: {fact_excerpt}", max_chars)

    if "speq" in text or ("prd" in text and "mcp" in text):
        summary = (
            f"{clean_title}: 제품 명세를 PRD로 정리하고 MCP로 에이전트에 전달하는 "
            "협업 도구 신호입니다. 기획-개발 핸드오프 자동화 가능성을 확인하세요."
        )
    elif is_model_release_signal(text):
        summary = (
            f"{clean_title}: 새 LLM/모델 출시 또는 업데이트 신호입니다. 성능, 가격, "
            "API 변화와 에이전트 적용 가능성을 우선 확인하세요."
        )
    elif category == "harness_engineering":
        summary = (
            f"{clean_title}: 에이전트 하네스/런타임 운영 신호입니다. 오케스트레이션, "
            "도구 호출, 평가, 관찰성, 장시간 실행 안정성을 우선 확인하세요."
        )
    elif category == "coding_agent":
        summary = (
            f"{clean_title}: 코딩 에이전트와 개발 자동화 관련 신호입니다. 코드 생성, "
            "리뷰, 명세 기반 작업에 실제로 쓸 수 있는지 확인하세요."
        )
    elif category == "agent_framework":
        summary = (
            f"{clean_title}: 에이전트 프레임워크 또는 운영 방식 관련 신호입니다. "
            "메모리, 도구 호출, 평가, 배포 안정성에 미치는 영향을 확인하세요."
        )
    elif category == "research":
        summary = (
            f"{clean_title}: 연구/논문 기반 기술 신호입니다. 벤치마크 재현성과 "
            "오픈소스 구현으로 이어질 가능성을 확인하세요."
        )
    elif category == "benchmark":
        summary = (
            f"{clean_title}: 모델 또는 에이전트 평가 신호입니다. 기존 벤치마크 대비 "
            "성능 차이와 실제 업무 적용성을 확인하세요."
        )
    elif category == "model":
        summary = (
            f"{clean_title}: LLM 모델 업데이트 신호입니다. 성능, 비용, API 호환성, "
            "에이전트 워크플로 적용 영향을 추적하세요."
        )
    else:
        summary = (
            f"{clean_title}: Agent/AI 생태계에서 관찰된 신호입니다. 실제 출시 여부, "
            "사용자 반응, 기존 도구 대비 차별점을 확인하세요."
        )
    return truncate_text(summary, max_chars)


def detailed_korean_summary_for_report(
    raw: RawItem,
    summary: str,
    category: str,
    maturity: str,
    impact: str,
    signal_strength: int,
    tag_flags: dict[str, bool],
    insight: str,
    max_chars: int = 3200,
) -> str:
    title = clean_report_title(raw.title)
    source_digest = translated_source_digest(raw, summary, category)
    source_bullets = source_detail_bullets(raw, category)
    tags = ", ".join(f"#{tag}" for tag, enabled in tag_flags.items() if enabled) or f"#{category}"
    related_context = source_signal_context(raw)
    source_detail_section = "\n".join(f"- {bullet}" for bullet in source_bullets)
    detail = (
        "핵심 정리\n"
        f"- {summary}\n"
        f"- 원천: {raw.source_name}"
        f"{related_context}\n"
        f"- 분류: {category} / 성숙도: {maturity} / 영향도: {impact} / 신호 {signal_strength}/5\n\n"
        "원문 상세 요약\n"
        f"{source_detail_section}\n\n"
        "한글 정리\n"
        f"- {title}은(는) {source_digest}\n"
        f"- 주요 태그: {tags}\n\n"
        "인사이트\n"
        f"- {insight}\n\n"
        "확인 포인트\n"
        "- 원문에서 실제 출시 여부, 코드/논문/제품 근거, 가격이나 API 변경 여부를 확인하세요.\n"
        "- 하네스나 에이전트 운영에 적용할 경우 권한, 보안 경계, 평가 기준을 함께 점검하세요."
    )
    return truncate_text(detail, max_chars)


def source_detail_bullets(raw: RawItem, category: str, max_bullets: int = 8) -> list[str]:
    cleaned = clean_report_text(raw.summary)
    if not cleaned:
        return [translated_source_digest(raw, clean_report_title(raw.title), category)]
    sentences = [
        sentence.strip(" .")
        for sentence in SENTENCE_SPLIT_RE.split(cleaned)
        if sentence.strip() and not is_summary_noise(sentence)
    ]
    if not sentences:
        sentences = [cleaned]
    bullets: list[str] = []
    for sentence in sentences:
        bullet = detail_sentence_to_korean(sentence)
        if bullet and bullet not in bullets:
            bullets.append(bullet)
        if len(bullets) >= max_bullets:
            break
    return bullets or [translated_source_digest(raw, clean_report_title(raw.title), category)]


def detail_sentence_to_korean(sentence: str) -> str:
    text = sentence.strip()
    lowered = text.lower()
    if not text:
        return ""
    if is_korean_text(text):
        return truncate_text(text, 320)
    if "collaborative web-based repository" in lowered and "specification" in lowered:
        return "Speq는 제품 specification을 관리하는 협업형 웹 저장소입니다."
    if "peppers you with questions" in lowered:
        return "새 프로젝트를 충분히 이해할 때까지 질문을 던져 요구사항과 목표를 구체화합니다."
    if "comprehensive speq" in lowered or "can become a prd" in lowered:
        return "정리된 Speq는 PRD로 변환하거나 동료와 공유/협업할 수 있고, MCP를 통해 에이전트에게 handoff할 수 있습니다."
    if "vision" in lowered and "navigation flow" in lowered:
        return "비전, navigation flow, product requirements, logic, tech requirements를 정의하도록 돕습니다."
    if "easy to edit" in lowered and "version" in lowered:
        return "시간이 지나며 내용을 편집하고, 버전 관리하고, 요구사항을 발전시키기 쉽게 설계됐다고 설명합니다."
    if "microsoft" in lowered and "free" in lowered:
        return "Microsoft 지원 덕분에 현재는 무료로 제공된다고 설명합니다."
    if "sandbox" in lowered and "approval" in lowered:
        return "Codex 운영에서 sandboxing, 승인 정책, 네트워크 제어, telemetry 같은 안전장치를 함께 다룹니다."
    if "network" in lowered and "telemetry" in lowered:
        return "네트워크 접근 제어와 agent-native telemetry를 운영 가시성과 통제 장치로 제시합니다."
    return english_detail_fallback(text)


def english_detail_fallback(sentence: str) -> str:
    compact = truncate_text(sentence, 260)
    replacements = (
        ("shared how", "공유한 내용은"),
        ("released", "출시"),
        ("announced", "발표"),
        ("helps", "돕는다는 점"),
        ("framework", "프레임워크"),
        ("agent", "에이전트"),
        ("model", "모델"),
        ("tool", "도구"),
        ("workflow", "워크플로"),
        ("evaluation", "평가"),
        ("observability", "관찰성"),
    )
    translated = compact
    for source, target in replacements:
        translated = re.sub(source, target, translated, flags=re.IGNORECASE)
    if translated == compact:
        return f"원문은 {compact}라고 설명합니다."
    return f"원문은 {translated}라고 설명합니다."


def translated_source_digest(raw: RawItem, summary: str, category: str) -> str:
    cleaned_body = clean_report_text(raw.summary)
    if cleaned_body and is_korean_text(cleaned_body):
        return f"{select_fact_sentences(cleaned_body)} 내용을 다룹니다."
    if category == "model":
        return "모델 성능, 도구 사용, 비용 또는 API 변화와 관련된 소식입니다."
    if category == "coding_agent":
        return "코딩 에이전트의 실행 방식, 개발 워크플로, 코드 생성/리뷰 자동화와 관련된 소식입니다."
    if category == "harness_engineering":
        return "에이전트 하네스, 실행 격리, 승인 흐름, 관찰성, 평가 체계와 관련된 소식입니다."
    if category == "agent_framework":
        return "에이전트 프레임워크나 오케스트레이션 구조와 관련된 소식입니다."
    if category == "research":
        return "논문이나 연구 프로젝트를 기반으로 한 기술 신호입니다."
    if category == "benchmark":
        return "모델이나 에이전트 성능 평가와 관련된 소식입니다."
    if category == "tooling":
        return "개발자 도구, CLI, IDE, 운영 도구와 관련된 소식입니다."
    return f"{summary} 내용을 중심으로 정리한 Agent/AI 트렌드입니다."


def source_signal_context(raw: RawItem) -> str:
    context = []
    for key, label in (("points", "HN 점수"), ("comments", "댓글"), ("score", "커뮤니티 점수"), ("stars", "stars")):
        value = raw.metadata.get(key)
        if value not in (None, ""):
            context.append(f"{label} {value}")
    if not context:
        return ""
    return f" ({', '.join(context)})"


def news_fact_excerpt(title: str, body: str, max_chars: int = 190) -> str:
    cleaned = body.strip()
    if not cleaned:
        return ""
    lowered = f"{title} {cleaned}".lower()
    if is_channel_promo_summary(title, cleaned):
        return title_news_digest(title)
    if "speq" in lowered or ("prd" in lowered and "mcp" in lowered):
        return "제품 명세를 PRD로 정리하고 MCP로 에이전트에 전달하는 협업 도구입니다."
    if is_korean_text(cleaned):
        return truncate_text(select_fact_sentences(cleaned), max_chars)
    if is_model_release_signal(lowered):
        return english_model_release_excerpt(title, cleaned)
    if is_harness_engineering_signal(lowered):
        return english_harness_excerpt(title, cleaned)
    if "coding agent" in lowered or "codex" in lowered or "claude code" in lowered:
        return english_coding_agent_excerpt(title, cleaned)
    return ""


def is_channel_promo_summary(title: str, body: str) -> bool:
    return (
        title.lower().startswith(("ai뉴스", "it뉴스"))
        and contains_any(
            body.lower(),
            "뉴스레터",
            "무료 강의",
            "목차",
            "00:00",
            "출처 모아보기",
            "제보 메일",
        )
    )


def title_news_digest(title: str) -> str:
    topic = clean_report_title(title)
    if " - " in topic:
        topic = topic.split(" - ", 1)[1].strip()
    topic = re.sub(r"\s*등\s*$", "", topic).strip()
    return f"{topic} 등을 다룬 AI 뉴스 요약입니다."


def select_fact_sentences(text: str) -> str:
    sentences = [
        sentence.strip(" .")
        for sentence in SENTENCE_SPLIT_RE.split(text)
        if sentence.strip() and not is_summary_noise(sentence)
    ]
    if not sentences:
        return text
    selected = [sentences[0]]
    if len(sentences) > 1 and len(f"{sentences[0]}. {sentences[1]}") <= 190:
        selected.append(sentences[1])
    return ". ".join(selected)


def is_korean_text(text: str) -> bool:
    return bool(re.search(r"[\uac00-\ud7a3]", text))


def english_harness_excerpt(title: str, body: str) -> str:
    lowered = f"{title} {body}".lower()
    subject = "Momental" if "momental" in lowered else clean_report_title(title)
    features = []
    if "agent harness" in lowered:
        features.append("agent harness")
    if "context graph" in lowered:
        features.append("context graph")
    if "mcp" in lowered:
        features.append("MCP handoff")
    if "tool calling" in lowered or "tool use" in lowered:
        features.append("tool use")
    if "observability" in lowered or "tracing" in lowered:
        features.append("observability")
    if "subagent" in lowered or "multi-agent" in lowered or "cloud agents" in lowered:
        features.append("multi-agent operation")
    feature_text = ", ".join(dict.fromkeys(features)) or "agent operation"
    return f"{subject} 기반 {feature_text} 하네스를 소개한 에이전트 운영 데모입니다."


def english_model_release_excerpt(title: str, body: str) -> str:
    lowered = f"{title} {body}".lower()
    subject = model_subject(title, body)
    details = []
    if "tool" in lowered:
        details.append("도구 사용")
    if "coding" in lowered or "agent" in lowered:
        details.append("코딩 에이전트 성능")
    if "api" in lowered:
        details.append("API")
    if "price" in lowered or "pricing" in lowered or "cost" in lowered:
        details.append("요금")
    if details:
        return f"{subject} 모델 업데이트에서 {', '.join(details)} 변화가 핵심으로 언급됐습니다."
    return f"{subject} 관련 모델 업데이트가 공개됐습니다."


def english_coding_agent_excerpt(title: str, body: str) -> str:
    lowered = f"{title} {body}".lower()
    if "goal" in lowered:
        return "목표를 입력하면 완료될 때까지 작업을 반복 실행하는 코딩 에이전트 기능입니다."
    if "spec" in lowered or "prd" in lowered:
        return "명세와 요구사항을 에이전트 작업 입력으로 정리하는 개발 워크플로 도구입니다."
    return "코드 생성, 리뷰, 작업 자동화를 다루는 코딩 에이전트 업데이트입니다."


def model_subject(title: str, body: str) -> str:
    text = f"{title} {body}"
    match = re.search(r"\b(GPT[-\s]?\d+(?:\.\d+)?)\b", text, re.IGNORECASE)
    if match:
        return match.group(1).replace("-", " ")
    match = re.search(r"\b(Grok|Gemini|Claude|Opus)\s*[\w.]*\b", text, re.IGNORECASE)
    if match:
        return match.group(0).strip()
    return clean_report_title(title)


def clean_report_title(title: str) -> str:
    cleaned = clean_report_text(title)
    cleaned = TITLE_PREFIX_RE.sub("", cleaned).strip()
    return cleaned or title.strip()


def is_hot_model_update(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in HOT_MODEL_TERMS) or bool(hot_entities(lowered))


def is_model_release_signal(text: str) -> bool:
    lowered = text.lower()
    model_context_terms = (
        "model",
        "llm",
        "api",
        "pricing",
        "price",
        "cost",
        "release",
        "released",
        "launch",
        "launched",
        "announce",
        "announced",
        "신모델",
        "모델",
        "요금",
        "가격",
    )
    has_model_context = contains_any(lowered, *model_context_terms)
    if re.search(r"\bgpt[-\s]?\d", lowered) and has_model_context:
        return True
    if re.search(r"\b(grok|gemini)\s*\d", lowered) and has_model_context:
        return True
    if "opus" in lowered and has_model_context:
        return True
    if re.search(r"\bclaude\s+(\d|opus|sonnet|haiku)", lowered) and has_model_context:
        return True
    has_model_word = "model" in lowered or "모델" in lowered
    has_major_provider = any(term in lowered for term in ("openai", "anthropic", "google"))
    has_release_word = any(term in lowered for term in HOT_RELEASE_TERMS)
    return has_model_word and has_major_provider and has_release_word


def is_model_focused_signal(text: str) -> bool:
    lowered = text.lower()
    if contains_any(lowered, "agent harness", "mcp", "orchestration", "subagent", "langgraph"):
        return False
    return bool(
        re.search(r"\b(open|closed|frontier|local)?\s*models?\b", lowered)
        or re.search(r"\bglm[-\s]?\d", lowered)
        or re.search(r"\bminimax\b", lowered)
    )


def select_summary_sentences(sentences: list[str], max_chars: int) -> str:
    selected = [sentences[0]]
    preferred = next((sentence for sentence in sentences[1:] if is_priority_sentence(sentence)), None)
    fallback = sentences[1] if len(sentences) > 1 else None
    second = preferred or fallback
    if second:
        candidate = f"{selected[0]} {second}".strip()
        if len(candidate) <= max_chars:
            selected.append(second)
    return " ".join(selected)


def is_priority_sentence(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(term in lowered for term in SUMMARY_PRIORITY_TERMS)


def clean_report_text(value: str) -> str:
    text = html.unescape(value or "")
    text = HTML_TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = REFERENCE_PARENS_RE.sub("", text)
    text = URL_RE.sub("", text)
    text = WHITESPACE_RE.sub(" ", text).strip()
    text = SPEC_HANDOFF_RE.sub("It can become a PRD or be handed off to an agent via MCP.", text)
    text = WHITESPACE_RE.sub(" ", text).strip()
    return LEADING_NOISE_RE.sub("", text).strip()


def is_summary_noise(sentence: str) -> bool:
    lowered = sentence.lower()
    return lowered in {"thanks", "cheers"} or lowered.startswith("please give it a try")


def truncate_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return value[:max_chars]
    truncated = value[: max_chars - 3].rstrip()
    if " " in truncated:
        candidate = truncated.rsplit(" ", 1)[0]
        if len(candidate) >= max_chars // 2:
            truncated = candidate
    return f"{truncated}..."


def classify_category(text: str) -> str:
    lowered = text.lower()
    if is_ai_hardware_tooling_signal(lowered):
        return "tooling"
    if is_model_release_signal(lowered) or is_model_focused_signal(lowered):
        return "model"
    if is_harness_engineering_signal(lowered):
        return "harness_engineering"
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


def is_harness_engineering_signal(text: str) -> bool:
    return contains_any(text.lower(), *HARNESS_ENGINEERING_TERMS)


def is_ai_hardware_tooling_signal(text: str) -> bool:
    lowered = text.lower()
    return contains_any(
        lowered,
        "workstation",
        "워크스테이션",
        "ai station",
        "zgx",
        "gpu",
        "npu",
        "클러스터",
        "clustering",
    )


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
    low_community_engagement = is_low_engagement_community_item(raw)
    score = 1
    if source_credibility >= 0.8 and not low_community_engagement:
        score += 1
    if any(token in text for token in ["agent", "codex", "claude code", "autonomous", "framework"]):
        score += 1
    if is_harness_engineering_signal(text):
        score += 1
    if (
        any(token in text for token in ["release", "launched", "benchmark", "paper", "github"])
        and not low_community_engagement
    ):
        score += 1
    if star_count(raw.metadata.get("stars")) >= 100:
        score += 1
    if raw.title.lower() in history_text.lower():
        score -= 1
    return max(1, min(5, score))


def is_low_engagement_community_item(raw: RawItem) -> bool:
    if raw.source_type == "hn_algolia":
        if "points" not in raw.metadata and "comments" not in raw.metadata:
            return False
        return star_count(raw.metadata.get("points")) < 10 and star_count(raw.metadata.get("comments")) < 3
    if raw.source_type == "reddit_json":
        if "score" not in raw.metadata:
            return False
        return star_count(raw.metadata.get("score")) < 10
    return False


def star_count(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def classify_tag_flags(raw: RawItem, category: str) -> dict[str, bool]:
    text = f"{raw.title} {raw.summary} {raw.source_name} {raw.url}".lower()
    provider_text = clean_report_text(f"{raw.title} {raw.summary}").lower()
    if category == "harness_engineering":
        provider_text = raw.title.lower()
    flags = {tag: False for tag in TAG_COLUMNS}

    if category in flags:
        flags[category] = True
    flags["model"] = (
        not is_ai_hardware_tooling_signal(text)
        and (
            category == "model"
            or (category != "harness_engineering" and is_model_release_signal(text))
        )
    )
    flags["coding_agent"] = category == "coding_agent" or contains_any(
        text, "codex", "coding agent", "claude code", "cursor", "코딩 에이전트"
    )
    flags["agent_framework"] = category == "agent_framework" or contains_any(
        text, "agent framework", "agentic framework", "langgraph", "crewai", "smolagent"
    )
    flags["harness_engineering"] = category == "harness_engineering" or is_harness_engineering_signal(text)
    flags["agentic"] = flags["harness_engineering"] or contains_any(
        text, "agentic", "agentic ai", "에이전틱"
    )
    flags["autonomous_agent"] = contains_any(text, "autonomous", "자율", "자동 반복", "long-running")
    flags["orchestration"] = contains_any(
        text, "orchestration", "routing", "multi-agent", "multi agent", "langgraph", "오케스트레이션"
    )
    flags["subagent"] = contains_any(text, "subagent", "sub-agent", "worker agent", "하위 에이전트")
    flags["research"] = category == "research" or contains_any(text, "arxiv", "paper", "논문", "research")
    flags["benchmark"] = category == "benchmark" or contains_any(
        text, "benchmark", "leaderboard", "eval", "평가", "벤치마크"
    )
    flags["evaluation"] = flags["benchmark"] or contains_any(
        text, "evaluation", "eval", "evals", "eval harness", "평가", "테스트셋"
    )
    flags["observability"] = contains_any(
        text, "observability", "tracing", "trace", "monitoring", "langsmith", "관찰성", "추적"
    )
    flags["release"] = contains_any(
        text, "release", "released", "launch", "launched", "announced", "출시", "공개", "추가됨"
    )
    flags["pricing"] = contains_any(text, "price", "pricing", "cost", "요금", "가격", "비용")
    flags["api"] = contains_any(text, "api")
    flags["mcp"] = contains_any(text, "mcp")
    flags["plugin"] = contains_any(text, "plugin", "plugins", "extension", "플러그인", "확장")
    flags["memory"] = contains_any(text, "memory", "메모리", "context window", "컨텍스트")
    flags["workflow"] = contains_any(
        text, "workflow", "prd", "spec", "goal", "/goal", "명세", "목표", "워크플로", "monorepo"
    )
    flags["security"] = contains_any(text, "security", "secure", "dangerous", "보안", "위험")
    flags["multimodal"] = contains_any(text, "multimodal", "image", "video", "audio", "이미지", "영상")
    flags["image"] = contains_any(text, "image", "이미지", "nano banana")
    flags["video"] = contains_any(text, "video", "youtube", "영상")
    flags["tooling"] = (
        category == "tooling"
        or is_ai_hardware_tooling_signal(text)
        or contains_any(text, "tool", "cli", "ide", "도구")
    )
    flags["tool_use"] = contains_any(
        text, "tool use", "tool calling", "function calling", "tools", "도구 호출"
    )
    flags["cli"] = contains_any(text, "cli", "command line", "터미널")
    flags["ide"] = contains_any(text, "ide", "vscode", "cursor")
    flags["github"] = raw.source_type == "github_search" or "github.com" in text
    flags["youtube"] = "youtube" in text or "youtu.be" in text
    flags["community"] = raw.source_type in {"hn_algolia", "reddit_json"} or contains_any(
        text, "geeknews", "hacker news", "reddit"
    )
    flags["paper"] = raw.source_type == "arxiv" or contains_any(text, "paperswithcode", "paper", "논문")
    flags["open_source"] = flags["github"] or contains_any(text, "open source", "오픈소스")

    flags["openai"] = contains_entity(provider_text, "openai", "gpt", "chatgpt", "codex") or source_is_provider(raw, "openai")
    flags["anthropic"] = contains_entity(provider_text, "anthropic", "claude", "opus") or source_is_provider(raw, "anthropic")
    flags["google"] = contains_entity(provider_text, "google", "gemini", "nano banana") or source_is_provider(raw, "google")
    flags["xai"] = contains_entity(provider_text, "xai", "grok")
    flags["meta"] = contains_entity(provider_text, "meta", "llama")
    flags["huggingface"] = contains_entity(provider_text, "hugging face", "huggingface") or source_is_provider(raw, "huggingface")
    return flags


def contains_any(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def contains_entity(text: str, *terms: str) -> bool:
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text)
        for term in terms
    )


def source_is_provider(raw: RawItem, provider: str) -> bool:
    source_id = raw.source_id.lower()
    source_name = raw.source_name.lower()
    if provider == "openai":
        return source_id.startswith("openai") or source_name.startswith("openai")
    if provider == "anthropic":
        return source_id.startswith("anthropic") or source_name.startswith("anthropic")
    if provider == "google":
        return source_id == "google_ai_blog" or source_name == "google ai blog"
    if provider == "huggingface":
        return source_id.startswith("huggingface") or source_name.startswith("hugging face")
    return False


def tags_from_flags(flags: dict[str, bool]) -> list[str]:
    return [f"#{tag}" for tag in TAG_COLUMNS if flags.get(tag)]


def normalize_item(raw: RawItem, source_credibility: float, history_text: str) -> TrendItem:
    text = f"{raw.title} {raw.summary}"
    score = signal_score(raw, source_credibility, history_text)
    category = classify_category(text)
    summary = summarize_korean_for_report(raw.title, raw.summary, category)
    tag_flags = classify_tag_flags(raw, category)
    maturity = classify_maturity(text)
    impact = impact_from_score(score)
    insight = why_it_matters(category, score, raw.title, raw.summary, summary, tag_flags)
    return TrendItem(
        title=raw.title,
        url=raw.url,
        source=raw.source_name,
        image_url=image_url(raw),
        published_at=raw.published_at,
        summary=summary,
        detail_summary=detailed_korean_summary_for_report(
            raw,
            summary,
            category,
            maturity,
            impact,
            score,
            tag_flags,
            insight,
        ),
        category=category,
        maturity=maturity,
        impact=impact,
        signal_strength=score,
        tags=tags_from_flags(tag_flags),
        tag_flags=tag_flags,
        why_it_matters=insight,
        related_items=[],
    )


def image_url(raw: RawItem) -> str | None:
    value = raw.metadata.get("image_url")
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value.startswith(("http://", "https://")):
        return value
    return None


def why_it_matters(
    category: str,
    score: int,
    title: str = "",
    source_summary: str = "",
    report_summary: str = "",
    tag_flags: dict[str, bool] | None = None,
) -> str:
    flags = tag_flags or {}
    text = f"{title} {source_summary} {report_summary}".lower()
    if "/goal" in text or "목표 기반 자동 반복" in text:
        return (
            "/goal처럼 목표 기반 자동 반복이 CLI에 들어오면 에이전트가 긴 작업을 스스로 "
            "이어갈 수 있습니다. 종료 조건, 실패 복구, 사람 리뷰 시점을 먼저 점검하세요."
        )
    if "speq" in text or ("prd" in text and "mcp" in text):
        return (
            "요구사항 명세가 에이전트 입력 품질을 좌우하는 흐름입니다. PRD 품질, 변경 이력, "
            "MCP 전달 방식이 실제 개발 속도와 재작업률을 줄이는지 확인하세요."
        )
    if is_model_release_signal(text):
        return (
            "모델 성능, 요금, API 변화가 에이전트 제품의 비용 구조와 기능 범위를 바꿀 수 "
            "있습니다. 벤치마크와 실제 도구 사용 성능을 확인하세요."
        )
    if category == "harness_engineering":
        return (
            "하네스 변화는 에이전트를 실험에서 운영 단계로 옮기는 핵심 신호입니다. 평가, "
            "관찰성, 도구 권한, 실패 복구, 사람 승인 지점을 함께 점검하세요."
        )
    if flags.get("benchmark"):
        return (
            "벤치마크 신호는 모델 선택과 에이전트 하네스 설계의 기준이 됩니다. 평가 데이터, "
            "재현 가능성, 실제 코드베이스 성능 차이를 분리해서 확인하세요."
        )
    if flags.get("memory"):
        return (
            "장기 메모리와 컨텍스트 관리는 장시간 실행 에이전트의 품질을 좌우합니다. 저장 "
            "범위, 만료 정책, 잘못된 기억을 되돌리는 방법을 확인하세요."
        )
    if category == "coding_agent":
        return (
            "개발자가 명세 작성, 코드 생성, 리뷰를 맡기는 범위가 넓어질 수 있습니다. "
            "내부 코드베이스 적용성, 보안 경계, 리뷰 비용을 확인하세요."
        )
    if category == "agent_framework":
        return (
            "에이전트의 메모리, 도구 호출, 평가/관찰성 설계에 직접 영향을 줍니다. "
            "기존 프레임워크 대비 운영 복잡도와 안정성을 비교하세요."
        )
    if category == "research":
        return (
            "아직 제품화 전 신호일 수 있습니다. 공개 코드, 벤치마크 재현성, 실제 도구 "
            "연결 사례가 나오는지 추적하세요."
        )
    if score >= 4:
        return (
            "단기 Agent/AI 전략에 반영할 만한 신호입니다. 사용자 반응, 가격 변화, "
            "대체 도구 대비 차별점을 함께 확인하세요."
        )
    return "초기 신호입니다. 반복 보도, 실제 사용자 사례, 공개 데모가 이어지는지 확인하세요."
