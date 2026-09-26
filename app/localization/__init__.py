from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_translations: dict[str, dict[str, str]] = {}


def _load_translations():
    global _translations
    if _translations:
        return
    for lang in ["fa", "en"]:
        path = Path(__file__).parent / f"{lang}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                _translations[lang] = json.load(f)
        else:
            _translations[lang] = {}
            logger.warning(f"Translation file {path} not found")


def get_text(key: str, lang: str = "en", **kwargs: Any) -> str:
    _load_translations()
    text = _translations.get(lang, {}).get(key)
    if text is None:
        text = _translations.get("en", {}).get(key)
    if text is None:
        logger.warning(f"Missing translation key: {key} for lang {lang}")
        return key
    try:
        return text.format(**kwargs)
    except KeyError as e:
        logger.error(f"Missing placeholder {e} for key {key} in {lang}")
        # Return the text with placeholders replaced by empty strings to avoid leaking braces
        # This is a safety fallback - log the error but don't expose raw {placeholder} to users
        safe_text = text
        for missing_key in e.args:
            safe_text = safe_text.replace(f"{{{missing_key}}}", "[...]")
        return safe_text
