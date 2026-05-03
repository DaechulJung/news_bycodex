---
name: collect-search
description: Discover Agent/AI trend items from keyword-driven search sources.
---

# Collect Search

Input: `configs/keywords.yaml`.

Output: `data/raw/YYYY-MM-DD/search.jsonl`.

Rules:
- Search priority keywords first.
- Keep query text in metadata.
- Exclude generic SEO pages when they match known noise patterns.
- Promote search findings only after normalization and scoring.
