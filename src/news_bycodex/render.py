from pathlib import Path
import re
from urllib.parse import urlparse

from jinja2 import Environment, PackageLoader, select_autoescape

from news_bycodex.analysis import canonical_url, summarize_for_report
from news_bycodex.io import ensure_dir
from news_bycodex.models import ReportData


RELATED_URL_RE = re.compile(r"https?://[^\s)>,]+")


def safe_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        return value
    return "#"


def related_url(value: str) -> str:
    match = RELATED_URL_RE.search(value)
    if not match:
        return ""
    return match.group(0).rstrip(".,")


def related_label(value: str) -> str:
    url = related_url(value)
    if not url:
        return ""
    label = value.replace(url, "").strip(" :-")
    return label or url


def related_links(items: list[str], current_url: str = "") -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    current_key = canonical_url(current_url) if current_url else ""
    for item in items:
        url = related_url(item)
        if not url:
            continue
        key = canonical_url(url)
        if current_key and key == current_key:
            continue
        if key in seen:
            continue
        seen.add(key)
        links.append({"url": url, "label": related_label(item)})
    return links


def display_summary(value: str, title: str = "") -> str:
    return summarize_for_report(title, value)


def display_detail_summary(item) -> str:
    if item.detail_summary:
        return item.detail_summary
    summary = display_summary(item.summary, item.title)
    return (
        "핵심 정리\n"
        f"- {summary}\n\n"
        "인사이트\n"
        f"- {item.why_it_matters}\n\n"
        "확인 포인트\n"
        "- 원문 링크에서 실제 근거와 최신 상태를 확인하세요."
    )


def render_report(report: ReportData, output_dir: str | Path) -> Path:
    directory = Path(output_dir)
    ensure_dir(directory)
    env = Environment(
        loader=PackageLoader("news_bycodex", "templates"),
        autoescape=select_autoescape(["html", "xml", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["safe_url"] = safe_url
    env.filters["related_url"] = related_url
    env.filters["related_label"] = related_label
    env.filters["related_links"] = related_links
    env.filters["display_summary"] = display_summary
    env.filters["display_detail_summary"] = display_detail_summary
    template = env.get_template("report.html.j2")
    output = directory / f"{report.date}.html"
    output.write_text(template.render(report=report), encoding="utf-8")
    return output
