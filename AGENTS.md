# Repository Guidelines

## Project Structure & Module Organization

This repository is intended to become a Codex-driven daily Agent/AI trend intelligence harness. Keep the source layout explicit as the scaffold is added:

- `src/news_bycodex/agents/`: coordinator, collector, analyst, editor, and publisher agent logic.
- `src/news_bycodex/collectors/`: source adapters for RSS, crawling, search, GitHub Trending, Product Hunt, arXiv, Papers with Code, and community sources.
- `src/news_bycodex/skills/`: reusable collection and analysis skills used by subagents.
- `src/news_bycodex/templates/`: HTML report templates and shared styling.
- `data/raw/` and `data/processed/`: local collection snapshots and normalized trend records; avoid committing large generated data.
- `tests/`: unit and integration tests mirroring `src/` modules.

## Build, Test, and Development Commands

The repository currently has no committed build tooling. When adding the scaffold, expose the standard workflow through one command surface, preferably `Makefile` or package scripts:

- `make dev`: run a local daily-report harness against a small source set.
- `make test`: run the full test suite.
- `make lint`: run format, lint, and static checks.
- `make report DATE=2026-05-03`: generate one HTML trend report for a specific date.

Document any additional environment variables in `.env.example`.

## Coding Style & Naming Conventions

Use small modules with clear role boundaries: collection, normalization, scoring, synthesis, and publishing should not be mixed. Name collectors by source, for example `hacker_news.py`, `arxiv.py`, or `github_trending.py`. Name agent classes by role, such as `CoordinatorAgent`, `CollectorAgent`, `TrendAnalystAgent`, and `EditorAgent`. Keep configuration declarative in YAML, TOML, or JSON rather than hard-coded in agent prompts.

## Testing Guidelines

Add tests with each collector, scoring rule, and report-generation change. Use fixture files for external responses so tests do not depend on live websites. Prefer names such as `test_collectors_arxiv.py` and `test_trend_scoring.py`. Integration tests should verify that raw inputs produce normalized items, ranked trends, and a valid HTML output file.

## Commit & Pull Request Guidelines

No Git history exists yet, so use concise imperative commit messages, for example `Add arXiv collector` or `Create daily HTML report template`. Pull requests should include the purpose, sources affected, sample output when report rendering changes, and any new configuration keys. Link related issues and call out skipped sources or known data-quality limitations.

## Security & Configuration Tips

Do not commit API keys, cookies, browser profiles, or paid-search credentials. Keep source rate limits configurable. Treat crawler changes carefully: identify user agents, respect robots.txt where applicable, and prefer RSS or official APIs when available.
