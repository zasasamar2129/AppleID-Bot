from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def get_custom_emoji_id(emoji_id: str | None, enabled: bool) -> str | None:
    """
    Return the custom emoji ID if enabled and provided, otherwise None.
    Logs a warning when enabled but ID is missing.
    """
    if not enabled:
        return None
    if not emoji_id:
        logger.warning("Custom emoji enabled but emoji ID is not configured")
        return None
    return emoji_id
