# Araxis Syntax Blob Specification

## Overview
This document describes the **Araxis Merge "generic syntax highlighting" blob
format** as used and manipulated by the araxis_syntax_tool CLI. The blob is a
*flat JSON object* (string keys to string values) that encodes one or more
language definitions for the Araxis generic highlighter. Each language's
information is split across two kinds of keys:
- UUID-keyed entries (tied to a language UUID). The UUID is not always a literal UUID -- it's just a string identifier.
- filename-pattern-keyed entries (tied to the language's `filenamePattern` value).

The format permits an optional textual header `json:` before the JSON object;
the CLI accepts and emits this header according to a `--no-header` option.

---

## Top-level representation (flat JSON)
The Araxis blob is a single JSON object mapping string keys to string values. Example keys look like:

```
"file.patterns.<UUID>": "<semicolon-delimited filename patterns>",
"genericlanguage.description.<UUID>": "<display name>",
"keywords.*.<patternKeySuffix>": "<whitespace separated keywords>",
"keywords2.*.<patternKeySuffix>": "<keywords class 2>",
"keywords3.*.<patternKeySuffix>": "<operator symbols / group3>",
"keywords4.*.<patternKeySuffix>": "<single-line comment symbols>",
"keywords5.*.<patternKeySuffix>": "<multi-line comment start symbols>",
"keywords6.*.<patternKeySuffix>": "<multi-line comment end symbols>",
"keywords7.*.<patternKeySuffix>": "<isCaseSensitive> [no_backslash_escape]",
"keywords8.*.<patternKeySuffix>": "<keywords class 3>",
"lexer.*.<patternKeySuffix>": "generic"
```

Notes:
- All fields must be present for each language in a typical araxis blob, but in practice only `file.patterns.<UUID>` and `genericlanguage.description.<UUID>` are required to be non-empty for a language to be meaningful.
- `filenamePattern` is a semicolon-delimited string of file-glob patterns (e.g. `"*.src;*.pkg"`).
- Values are stored and read as strings. The `keywords7.*.*` value may contain two tokens: `"true"`/`"false"` followed optionally by the literal `no_backslash_escape`. See **keywords7** below.

---

## `patternKeySuffix` normalization rule (key naming)
Araxis keys that encode per-pattern values use a *pattern key suffix* rather than the raw `filenamePattern` string. In practice this suffix is derived from the `filenamePattern` by applying a simple rule used by the CLI and described here (also used by araxis_syntax_tool). The rule is:

1. Split the `filenamePattern` on `;` into tokens. (Example: `"*.bnl;*.bnh"` -> `["*.bnl","*.bnh"]`).
2. For the **first token only**, strip a leading literal `*.` if present; otherwise strip a single leading `*` if present. Leave subsequent tokens unchanged.
3. Join with `;` to form the `patternKeySuffix`. Example transforms:
   - `"*.bnl;*.bnh"` -> `"bnl;*.bnh"`
   - `"*.exp"` -> `"exp"`
   - `"*.src;*.pkg"` -> `"src;*.pkg"`

This suffix is what appears after the `keywords.*.` / `keywords2.*.` / etc. prefixes in the flat blob keys. When packing, the CLI performs the inverse operation heuristically to rebuild `filenamePattern` tokens (it prefixes the first token with `*.` when it looks like a file extension or plain token).

> Rationale: Araxis historically uses slightly different key naming for pattern-based keys; the tool uses this rule to make round-trip import/export identical for common patterns (especially those beginning with `*.`).

---

## Per-language JSON (unpacked) schema
The CLI writes and reads one JSON file per language when unpacking/packing. The schema is:

```json
{
  "uuid": "<UUID string>",
  "name": "<display name>",
  "filenamePattern": "<semicolon-delimited file patterns>",
  "keywordsClass1": "<whitespace-separated keywords>",
  "keywordsClass2": "<...>",
  "keywordsClass3": "<...>",
  "operatorSymbols": "<whitespace-separated operator tokens>",
  "singleLineCommentSymbols": "<...>",
  "multiLineCommentStartSymbols": "<...>",
  "multiLineCommentEndSymbols": "<...>",
  "isCaseSensitive": "true" | "false",
  "backslashIsAStringEscape": true | false,
  "lexer": "generic"
}
```

Notes:
- `isCaseSensitive` is stored as the literal strings `"true"` or `"false"` to match Araxis's convention.
- `backslashIsAStringEscape` is a **boolean** introduced to preserve the `no_backslash_escape` marker found in `keywords7.*.*`. When `false`, the packed blob will include `no_backslash_escape` after the case token (see **keywords7** section).
- The CLI enforces `filenamePattern` to be non-empty and validates `isCaseSensitive` to be `"true"` or `"false"` when loading per-language JSON files for packing/merging.

---

## `keywords7.*.<patternKeySuffix>` details (case & backslash behavior)
`keywords7` encodes two related settings in a single string value in the flat Araxis blob:
1. `isCaseSensitive` — `"true"` or `"false"` (required)
2. Optional token `no_backslash_escape` — if present, indicates that the language **does not** treat `\` as a string escape character.

Examples:
- `"true"` -> case-sensitive, backslash is an escape.
- `"false"` -> case-insensitive, backslash is an escape.
- `"true no_backslash_escape"` -> case-sensitive, backslash is **not** an escape.

The CLI unpacks this into the per-language fields `isCaseSensitive` and `backslashIsAStringEscape` (boolean) and writes it back when packing so round-trip is lossless.

---

## Merge (UPSERT) semantics
`merge <input_dir> <output_file>` implements the following UPSERT rules when applying per-language JSON files into an existing target blob:

1. If an incoming language UUID already exists in the target:
   - Delete the existing language's keys (both the `file.patterns.<UUID>` and `genericlanguage.description.<UUID>` entries and any pattern-keyed entries keyed by that language's **current** `filenamePattern`) and then add the incoming language’s keys as defined in the incoming file. This replaces the language definition.

2. If incoming language UUID does not exist in the target:
   - If the incoming `filenamePattern` conflicts (exact string match) with a `filenamePattern` already present in the target and that existing pattern belongs to a different UUID, **refuse to merge** and exit with an error. The tool requires the user to resolve pattern collisions manually outside the tool in this case.
   - If no conflict, add the incoming language as a new language to the target.

3. Languages present in the target but not part of the incoming set remain unchanged.

> Unique-ness is primarily enforced on the `filenamePattern` string value (treated as the canonical uniqueness key across languages). The display `name` is not required to be unique.

---

## CLI behavior / header handling / packing options
- `unpack <input_file> <output_dir>`: reads an Araxis blob (accepts optional `json:` header), writes one JSON per language into `output_dir` using a filesystem-safe rendition of the language name. If multiple languages map to the same sanitized filename, a short UUID-derived suffix is appended to avoid collisions.
- `pack <input_dir> <output_file>`: reads all `*.json` files in `input_dir` (simple validation applied) and writes a single Araxis blob to `output_file`. By default the output is minified and prefixed with `json: `. When `--no-header` is supplied, the output is pretty-printed with indent=2 and **no** `json:` prefix.
- `merge <input_dir> <output_file>`: applies UPSERT rules (see Merge section). If `output_file` does not exist, `merge` behaves like `pack` and creates a new blob containing the incoming languages.
- `--no-header`: omit the `json:` header and pretty-print the JSON when writing an Araxis blob.

---

## Examples

### Flat snippet (abridged)
```json
{
  "file.patterns.4C21...": "*.bnl;*.bnh",
  "genericlanguage.description.4C21...": "BrandNewLanguage (BNL)",
  "keywords.*.bnl;*.bnh": "BNL_KEYWORD1 BNL_KEYWORD2",
  "keywords7.*.bnl;*.bnh": "true no_backslash_escape",
  "lexer.*.bnl;*.bnh": "generic"
}
```

### Corresponding per-language JSON (unpacked)
```json
{
  "uuid": "4C21...",
  "name": "BrandNewLanguage (BNL)",
  "filenamePattern": "*.bnl;*.bnh",
  "keywordsClass1": "BNL_KEYWORD1 BNL_KEYWORD2",
  "isCaseSensitive": "true",
  "backslashIsAStringEscape": false,
  "lexer": "generic"
}
```

---

## Validation rules & common errors
- **Missing `filenamePattern`** in a per-language JSON causes packing to fail; filenamePattern must be non-empty.
- **Invalid `isCaseSensitive`** (not exactly `"true"` or `"false"`) is rejected on pack/merge input.
- **Duplicate `filenamePattern`** among incoming per-language JSON files is rejected at pack time (the CLI refuses to create a blob with duplicate filenamePattern values in the same batch).
- **Merge conflict**: during merge, if an incoming language has a `filenamePattern` that already exists for a different UUID in the target blob, the tool fails and asks the user to resolve the conflict manually.
