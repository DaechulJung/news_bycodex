---
name: collect-rss
description: Collect Agent/AI trend items from configured RSS or Atom feeds.
---

# Collect RSS

Input: `configs/sources.yaml`, `configs/keywords.yaml`.

Output: `data/raw/YYYY-MM-DD/<source_id>.jsonl`.

Rules:
- Prefer official RSS or Atom feeds.
- Filter by configured keywords when a source is broad.
- Keep raw titles, URLs, dates, summaries, and source metadata.
- Record source failures in `data/raw/YYYY-MM-DD/errors.jsonl`.
