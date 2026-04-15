"""
Language configuration loader.

Reads LANGUAGE environment variable (default: 'ko') and loads
the corresponding lang/{lang}.yaml file.

Usage:
    from scripts.lang_config import L

    print(L.tagging.empty_label)
    print(L.tagging.api_prompt.format(source_label="...", ...))

Supported languages:
    LANGUAGE=ko  (Korean, default)
    LANGUAGE=ja  (Japanese)
"""

import os
import yaml
from pathlib import Path


class _AttrDict(dict):
    """Dict with dot-notation access."""
    def __getattr__(self, key):
        try:
            val = self[key]
            return _AttrDict(val) if isinstance(val, dict) else val
        except KeyError:
            raise AttributeError(f"Language config has no key: '{key}'")

    def __missing__(self, key):
        raise KeyError(f"Language config has no key: '{key}'")


def _load(lang: str) -> _AttrDict:
    lang_file = Path(__file__).parent.parent / "lang" / f"{lang}.yaml"
    if not lang_file.exists():
        supported = [p.stem for p in lang_file.parent.glob("*.yaml")]
        raise FileNotFoundError(
            f"Language config '{lang}.yaml' not found. "
            f"Supported: {supported}"
        )
    with open(lang_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return _AttrDict(data)


_lang = os.environ.get("LANGUAGE", "ko").lower()
L = _load(_lang)
