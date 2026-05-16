---
name: collect-search
description: Discover Agent/AI trend items from generic manual web search.
---

# Collect Search

Automated workflow: `news-bycodex report` uses the `google_search` source type for keyword-based discovery.

The collector first tries Google's Custom Search JSON API when `GOOGLE_SEARCH_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID` are set. Because that API is closed to new customers, the collector falls back to Google News RSS keyword search for the last seven days when the API is unavailable or credentials are absent.

Input: `configs/keywords.yaml`.

Output: `data/raw/YYYY-MM-DD/google_search.jsonl`.

Rules:
- Search priority keywords first.
- Keep query text in metadata.
- Exclude generic SEO pages when they match known noise patterns.
- Promote search findings only after normalization and scoring.
- Treat Google News RSS as a discovery signal, not as primary-source confirmation.
