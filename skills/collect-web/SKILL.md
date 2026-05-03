---
name: collect-web
description: Collect public Agent/AI trend items from configured HTML sources.
---

# Collect Web

Input: `configs/sources.yaml`, `configs/keywords.yaml`.

Output: `data/raw/YYYY-MM-DD/<source_id>.jsonl`.

Rules:
- Use conservative request rates.
- Extract public links and titles only.
- Prefer stable CSS selectors in source config.
- Record blocked or failed sources without failing the whole run.
