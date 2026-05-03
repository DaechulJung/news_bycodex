from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from news_bycodex.io import ensure_dir
from news_bycodex.models import ReportData


def render_report(report: ReportData, output_dir: str | Path) -> Path:
    directory = Path(output_dir)
    ensure_dir(directory)
    env = Environment(
        loader=PackageLoader("news_bycodex", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("report.html.j2")
    output = directory / f"{report.date}.html"
    output.write_text(template.render(report=report), encoding="utf-8")
    return output
