import re
import logging
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger('validation')

# Regex constraint patterns
ATTACHMENT_DEEP_LINK_PATTERN = re.compile(r"^att-(\d+)-([a-z0-9_]+)$")
WEAPON_ALL_DEEP_LINK_PATTERN = re.compile(r"^allw-([a-z0-9_]+)__([a-zA-Z0-9_\-]+)__([a-z0-9_]+)$")

# Allowed enumerated modes based on general app context
ALLOWED_MODES = {'br', 'mp', 'zombies'}


def parse_attachment_deep_link(param: str) -> Tuple[Optional[int], str]:
    """
    Validates and parses the 'att-{id}-{mode}' deep link pattern.
    Returns (attachment_id, mode). Returns (None, 'br') if invalid.
    """
    match = ATTACHMENT_DEEP_LINK_PATTERN.match(param)
    if not match:
        logger.warning(f"Invalid attachment deep-link format: {param}")
        return None, 'br'

    try:
        att_id = int(match.group(1))
        mode = match.group(2)
        if mode not in ALLOWED_MODES:
            logger.warning(f"Disallowed mode in attachment deep-link: {mode}")
            mode = 'br'
        return att_id, mode
    except ValueError:
        return None, 'br'


def parse_all_weapons_deep_link(param: str) -> Tuple[Optional[str], Optional[str], str]:
    """
    Validates and parses the 'allw-{category}__{weapon}__{mode}' deep link pattern.
    Returns (category, weapon, mode). Returns (None, None, 'br') if invalid.
    """
    match = WEAPON_ALL_DEEP_LINK_PATTERN.match(param)
    if not match:
        logger.warning(f"Invalid all-weapons deep-link format: {param}")
        return None, None, 'br'

    category = match.group(1)
    weapon = match.group(2)
    mode = match.group(3)

    if mode not in ALLOWED_MODES:
        logger.warning(f"Disallowed mode in all-weapons deep-link: {mode}")
        mode = 'br'

    return category, weapon, mode


def safe_int(value: Any, default: int = 0) -> int:
    """
    Safely converts a value to integer, returning a default if conversion fails.
    Useful for callback_data string parsing.
    """
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return default
