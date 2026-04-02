# Localization Files

This directory contains UI translation files for Stellaris GUI Editor.

## Language Files

| File | Language | Status |
|------|----------|--------|
| `en.json` | English | ✅ Complete |

## How to Add a New Language

1. **Copy `TEMPLATE.json`** and rename it to your language code:
   - `de.json` — Deutsch
   - `fr.json` — Français
   - `es.json` — Español
   - `ru.json` — Русский
   - `ja.json` — 日本語
   - `ko.json` — 한국어
   - `pt_BR.json` — Português (Brasil)
   - `pl.json` — Polski
   - `it.json` — Italiano
   - `nl.json` — Nederlands

   Language codes follow [BCP-47](https://tools.ietf.org/html/bcp47).

2. **Copy all entries from `en.json`** into your file. The keys are Chinese strings (the source language); the values are your translations.

3. **Translate the values**, keeping the keys unchanged.

4. **Format rules:**
   - Keys and values are JSON strings — escape `"` as `\"`
   - Preserve `%s`, `%d`, `%.2f`, `{count}` placeholders exactly
   - Preserve `\n` line breaks where they appear in the original
   - Preserve HTML tags like `<b>`, `<i>`, `<a href=` in About dialog strings
   - Menu mnemonics like `&File`, `&Save` — place `&` before the letter for your language's shortcut
   - Do not translate: widget type names (`containerWindowType`, `iconType`, etc.), property names (`spriteType`, `orientation`, etc.), script keywords (`always = yes`)

5. **Test your translation** by launching the editor and switching to your language via Settings.

6. **Submit** a Pull Request to the main repository.

## File Format

```json
{
  "中文原文键": "Your language translation",
  "另一个中文字符串": "Another translation"
}
```

The app uses the Chinese text as the lookup key. If a key is missing from your file, the app falls back to English, then to the original Chinese.

## Notes

- You do **not** need to translate every string. Partial translations are accepted — untranslated strings show in English.
- The `_meta` object in TEMPLATE.json is optional but helpful for tracking contributors.
- If the app version is updated and new strings are added, compare with `en.json` to find what needs translating.

## Questions

Open an issue at the GitHub repository if you need help or have questions about specific strings.
