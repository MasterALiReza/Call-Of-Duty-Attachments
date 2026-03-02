import json
from pathlib import Path
from typing import Dict
from utils.logger import get_logger

logger = get_logger('i18n', 'app.log')

_translations: Dict[str, Dict] = {}
_locales_dir = Path(__file__).resolve().parent.parent / "locales"


def _load_translations(lang: str) -> Dict:
    if lang in _translations:
        return _translations[lang]
    locale_file = _locales_dir / f"{lang}.json"
    if not locale_file.exists():
        logger.warning(f"Locale file not found: {locale_file}")
        return {}
    try:
        with open(locale_file, 'r', encoding='utf-8') as f:
            _translations[lang] = json.load(f)
            return _translations[lang]
    except Exception as e:
        logger.error(f"Failed to load translations for '{lang}': {e}")
        return {}


def t(key: str, lang: str = 'fa', **kwargs) -> str:
    """Return localized text for the given key and language.

    Fallback order:
    1. locales/{lang}.json
    2. locales/{FALLBACK_LANG}.json
    3. config.config.MESSAGES (legacy Persian messages)
    4. The key itself
    """

    text = None
    try:
        # 1) Try current language
        translations = _load_translations(lang)
        text = translations.get(key)

        # 2) Fallback to global fallback language
        if text is None:
            try:
                from config.config import FALLBACK_LANG

                if lang != FALLBACK_LANG:
                    fallback_translations = _load_translations(FALLBACK_LANG)
                    text = fallback_translations.get(key)
            except Exception:
                # If config import fails for any reason, fall back to the key
                text = key
    except Exception:
        text = key

    if text is None:
        text = key

    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception as e:
            logger.error(f"Format error for key '{key}': {e}")
    return text


def kb(key: str, lang: str = 'fa') -> str:
    return t(key, lang)

def get_all_translations_for_key(key: str) -> list[str]:
    """Return all translations for a given key across all available locales."""
    result = set()
    for locale_file in _locales_dir.glob("*.json"):
        lang = locale_file.stem
        _load_translations(lang)
        if lang in _translations and key in _translations[lang]:
            result.add(_translations[lang][key])
            
    return list(result)

def build_regex_for_key(key: str) -> str:
    """Builds an exact-match Regex pattern matching ANY language's translation for the key.
    Includes support for optional trailing count like (10).
    """
    texts = get_all_translations_for_key(key)
    if not texts:
        texts = [key]  # safe fallback
        
    import re
    escaped = [re.escape(text) for text in texts]
    # Match exact text OR text followed by optional count in parentheses
    return r'^(' + '|'.join(escaped) + r')(?:\s*\(\d+\))?$'

def build_regex_for_keys(keys: list[str]) -> str:
    """Builds an exact-match Regex pattern matching ANY language's translation for ANY of the keys.
    Includes support for optional trailing count like (10).
    """
    all_texts = set()
    for key in keys:
        all_texts.update(get_all_translations_for_key(key))
    
    if not all_texts:
        all_texts = set(keys)
        
    import re
    escaped = [re.escape(text) for text in all_texts]
    return r'^(' + '|'.join(escaped) + r')(?:\s*\(\d+\))?$'

def reload_translations():
    _translations.clear()
    logger.info("Translation cache cleared")
