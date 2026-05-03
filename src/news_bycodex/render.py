from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment, PackageLoader, select_autoescape

from news_bycodex.io import ensure_dir
from news_bycodex.models import ReportData


def safe_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        return value
    return "#"


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
    template = env.get_template("report.html.j2")
    output = directory / f"{report.date}.html"
    output.write_text(template.render(report=report), encoding="utf-8")
    return output
