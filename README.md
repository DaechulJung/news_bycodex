# news_bycodex

Codex-native daily Agent/AI trend intelligence harness.

## Local MVP

Install dependencies:

```powershell
uv sync --extra dev
```

Run deterministic fixture mode:

```powershell
uv run news-bycodex report --date 2026-05-03 --offline-fixtures --output-dir reports
```

Run live collection:

```powershell
uv run news-bycodex report --date 2026-05-03 --limit-per-source 5 --output-dir reports
```

Outputs:

- `data/raw/YYYY-MM-DD/`
- `data/processed/YYYY-MM-DD/trends.jsonl`
- `reports/YYYY-MM-DD.html`
