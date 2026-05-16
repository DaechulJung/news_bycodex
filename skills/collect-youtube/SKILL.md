---
name: collect-youtube
description: Collect Agent/AI and developer trend videos from configured YouTube channel RSS feeds.
---

# Collect YouTube

Input: `configs/sources.yaml`, `configs/keywords.yaml`.

Output: `data/raw/YYYY-MM-DD/<source_id>.jsonl`.

Rules:
- Use `https://www.youtube.com/feeds/videos.xml?channel_id=<CHANNEL_ID>`.
- Keep title, watch URL, published date, summary, channel name, and source id.
- Filter broad IT channels with configured Agent/AI and developer-tool keywords.
- Summarize in Korean with only the core news point and a source link.
- Treat commentary videos as weak signals until confirmed by product, paper, or repository sources.
