---
name: collect-search
description: Discover Agent/AI trend items from generic manual web search.
---

# Collect Search

Manual/future workflow: this skill describes Codex-assisted generic web search discovery and is not automated by `news-bycodex report` in the MVP pipeline today.

This is separate from the implemented keyword-driven HN Algolia and GitHub API source types.

Input: `configs/keywords.yaml`.

Output: `data/raw/YYYY-MM-DD/search.jsonl`.

Rules:
- Search priority keywords first.
- Keep query text in metadata.
- Exclude generic SEO pages when they match known noise patterns.
- Promote search findings only after normalization and scoring.
- Treat the input/output contract as aspirational until a generic web search workflow is implemented.
