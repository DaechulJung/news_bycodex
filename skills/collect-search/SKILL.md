---
name: collect-search
description: Discover Agent/AI trend items from keyword-driven search sources.
---

# Collect Search

Manual/future workflow: this skill describes Codex-assisted discovery and is not automated by `news-bycodex report` in the MVP pipeline today.

Input: `configs/keywords.yaml`.

Output: `data/raw/YYYY-MM-DD/search.jsonl`.

Rules:
- Search priority keywords first.
- Keep query text in metadata.
- Exclude generic SEO pages when they match known noise patterns.
- Promote search findings only after normalization and scoring.
- Treat the input/output contract as aspirational until a search source type and collector are implemented.
