"""
应用程序 UI 国际化（i18n）模块。

设计原则
--------
- **以中文原文为键**：locale 文件存储 {原始中文: 目标语言翻译}，不需要维护单独的字符串 ID。
- **零成本中文回退**：当语言设置为 zh_CN 时 `_()` 直接返回原文，无额外开销。
- **静态 JSON 文件**：locale 文件放在 locales/<lang>.json，人类可读，社区可直接用文本编辑器贡献。
- **格式化友好**：支持 `%` 和 `.format()` 两种插值风格。
- **热切换**：调用 `set_language()` 立即生效（需重新 setText 等，推荐重启对话框生效）。

用法（UI 开发者）
-----------------
    from src.core.i18n import _

    label.setText(_('保存'))
    btn.setToolTip(_('撤销上一步操作'))
    msg = _('已加载 %d 个精灵图') % count
    msg2 = _('{count} 个控件已选中').format(count=n)

语言切换
--------
    from src.core.i18n import set_language, get_available_languages
    set_language('en')

社区贡献新语言
--------------
    在 locales/ 目录放置 <lang>.json，格式见 locales/TEMPLATE.json。
    lang 命名遵循 BCP-47：en, de, fr, es, ru, ja, ko, pt_BR 等。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
_LOCALES_DIR: Path = Path(__file__).parent.parent.parent / 'locales'

# ---------------------------------------------------------------------------
# 运行时状态
# ---------------------------------------------------------------------------
_current_lang: str = 'zh_CN'
_fallback_lang: str = 'en'                        # zh_CN 不存在翻译时的次级回退
_locale_cache: Dict[str, Dict[str, str]] = {}     # lang → {zh: target}
_change_callbacks: List = []                      # 语言切换时通知的回调列表


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def set_language(lang: str) -> None:
    """设置当前 UI 语言。

    Parameters
    ----------
    lang : str
        BCP-47 语言代码，如 ``'zh_CN'``、``'en'``、``'de'``。
        ``'zh_CN'`` 内置，无需 locale 文件。
    """
    global _current_lang
    prev = _current_lang
    _current_lang = lang
    if lang != 'zh_CN':
        _ensure_loaded(lang)
    if lang != prev:
        for cb in list(_change_callbacks):
            try:
                cb(lang)
            except Exception:
                pass
    logger.debug('i18n: language set to %s', lang)


def get_language() -> str:
    """返回当前 UI 语言代码。"""
    return _current_lang


def get_available_languages() -> List[str]:
    """返回可用语言列表（始终包含 zh_CN）。

    扫描 locales/ 目录下的所有 .json 文件（除 TEMPLATE.json）。
    """
    langs: List[str] = ['zh_CN']
    if _LOCALES_DIR.exists():
        for f in sorted(_LOCALES_DIR.glob('*.json')):
            if f.stem not in ('TEMPLATE', 'zh_CN') and f.stem not in langs:
                langs.append(f.stem)
    return langs


def get_language_display_name(lang: str) -> str:
    """返回语言的本地显示名称。"""
    _DISPLAY = {
        'zh_CN': '简体中文',
        'en':    'English',
        'de':    'Deutsch',
        'fr':    'Français',
        'es':    'Español',
        'ru':    'Русский',
        'ja':    '日本語',
        'ko':    '한국어',
        'pt_BR': 'Português (BR)',
        'pl':    'Polski',
        'it':    'Italiano',
        'nl':    'Nederlands',
    }
    return _DISPLAY.get(lang, lang)


def on_language_change(callback) -> None:
    """注册语言切换回调。callback(new_lang: str)。"""
    if callback not in _change_callbacks:
        _change_callbacks.append(callback)


def off_language_change(callback) -> None:
    """注销语言切换回调。"""
    if callback in _change_callbacks:
        _change_callbacks.remove(callback)


def t(text: str, *args, **kwargs) -> str:
    """翻译字符串到当前 UI 语言。

    Parameters
    ----------
    text : str
        原始中文字符串，作为翻译键。
    *args :
        传给 ``result % args`` 的位置参数。
    **kwargs :
        传给 ``result.format(**kwargs)`` 的关键字参数。

    Returns
    -------
    str
        翻译结果。若当前语言无对应翻译，回退到英文；
        若英文也无，返回原始中文字符串。
    """
    if not text:
        return text

    if _current_lang == 'zh_CN':
        result = text
    else:
        _ensure_loaded(_current_lang)
        translations = _locale_cache.get(_current_lang, {})
        result = translations.get(text)
        if result is None:
            # 回退到英文
            if _fallback_lang != _current_lang and _fallback_lang != 'zh_CN':
                _ensure_loaded(_fallback_lang)
                result = _locale_cache.get(_fallback_lang, {}).get(text, text)
            else:
                result = text

    if args:
        try:
            result = result % args
        except (TypeError, ValueError):
            result = result
    elif kwargs:
        try:
            result = result.format(**kwargs)
        except (KeyError, ValueError):
            result = result
    return result


# Short alias — the canonical way to translate in UI code
_ = t


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------

def _ensure_loaded(lang: str) -> None:
    """懒加载语言文件到缓存。"""
    if lang in _locale_cache:
        return
    locale_file = _LOCALES_DIR / f'{lang}.json'
    if locale_file.exists():
        try:
            with open(locale_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                _locale_cache[lang] = {str(k): str(v) for k, v in data.items()}
                logger.debug('i18n: loaded %d strings for lang=%s', len(data), lang)
            else:
                logger.warning('i18n: locale file %s has unexpected format', locale_file)
                _locale_cache[lang] = {}
        except Exception as exc:
            logger.warning('i18n: failed to load locale %s: %s', locale_file, exc)
            _locale_cache[lang] = {}
    else:
        logger.debug('i18n: no locale file for lang=%s', lang)
        _locale_cache[lang] = {}


def reload_language(lang: Optional[str] = None) -> None:
    """强制重新加载语言文件（开发/调试用）。"""
    target = lang or _current_lang
    if target in _locale_cache:
        del _locale_cache[target]
    _ensure_loaded(target)
