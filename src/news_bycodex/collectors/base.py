from collections.abc import Iterable
import re


def text_matches_keywords(text: str, keywords: Iterable[str]) -> bool:
    lowered = text.lower()
    for keyword in keywords:
        normalized = keyword.strip()
        if not normalized:
            continue
        if requires_token_boundary(normalized):
            pattern = rf"(?<![A-Za-z0-9]){re.escape(normalized)}(?![A-Za-z0-9])"
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True
        elif normalized.lower() in lowered:
            return True
    return False


def requires_token_boundary(keyword: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+#.]{0,2}", keyword))
