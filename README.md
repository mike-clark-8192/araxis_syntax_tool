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
"keywords.*.<patternKeySuffix>": "<whitespace separated keywords (class 1)>",
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

# `keywordsClass1`, `keywordsClass2`, `keywordsClass3` 

These are colorized differently by Araxis. When writing new syntax definitions,
the end-user will appreciate if you cluster similar keywords into the same class.

Let's use Python as an illustrative example:
Builtin and well-known functions go into `keywordsClass1`:
```
list dict set tuple print len open range str int
__repr__ __str__ __lt__ __le__ __gt__ __eq__ # etc.
args kwargs
```

Builtin and common constants might go into `keywordsClass2`:
```
True False None Ellipsis Error SyntaxError TypeError NotImplemented
List Dict Set Tuple Optional Union Any Callable Iterable Iterator Sequence Mapping
```

Control flow keywords might go into `keywordsClass3`:
```
if else elif for while break continue return import from as def class with try except finally raise yield
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

### Straight from the registry (sans the `json:` header prefix):
```json
{
    "file.patterns.4C21476D-F9BE-4345-AB8A-1F1EDBB8459B": "*.bnl;*.bnh",
    "file.patterns.twincat": "*.exp",
    "file.patterns.visualdataflex": "*.src;*.pkg",
    "genericlanguage.description.4C21476D-F9BE-4345-AB8A-1F1EDBB8459B": "BrandNewLanguage (BNL)",
    "genericlanguage.description.twincat": "TwinCAT or IEC",
    "genericlanguage.description.visualdataflex": "VisualDataFlex",
    "keywords.*.bnl;*.bnh": "BNL_KEYWORD1 BNL_KEYWORD2 BNL_KEYWORD3",
    "keywords.*.exp": "BOOL BYTE INT WORD DINT DWORD REAL STRING ARRAY POINTER_TO ADR MIN MAX DINT_TO_DWORD REAL_TO_DWORD AND OR NOT SEL",
    "keywords.*.src;*.pkg": "Class End_Class Use Set Get Object End_Object Forward is a of to If Begin End True False Procedure End_Procedure Function End_Function Function_Return On_Key Send Variant OverrideProperty InitialValue",
    "keywords2.*.bnl;*.bnh": "BNL_KEYWORD4 BNL_KEYWORD5 BNL_KEYWORD6",
    "keywords2.*.exp": "FOR END_FOR TO DO FROM VAR END_VAR FUNCTION_BLOCK VAR_INPUT ACTION END_ACTION",
    "keywords2.*.src;*.pkg": "OverrideProperty InitialValue ClassType",
    "keywords3.*.bnl;*.bnh": ":= + - * / ^ < > <= >= == = [ ] ( )",
    "keywords3.*.exp": ":= + - * / ^ < > <= >= == = [ ] ( )",
    "keywords3.*.src;*.pkg": "",
    "keywords4.*.bnl;*.bnh": "//",
    "keywords4.*.exp": "",
    "keywords4.*.src;*.pkg": "",
    "keywords5.*.bnl;*.bnh": "/* (*",
    "keywords5.*.exp": "(*",
    "keywords5.*.src;*.pkg": "",
    "keywords6.*.bnl;*.bnh": "*/ *)",
    "keywords6.*.exp": "*)",
    "keywords6.*.src;*.pkg": "",
    "keywords7.*.bnl;*.bnh": "true no_backslash_escape",
    "keywords7.*.exp": "false",
    "keywords7.*.src;*.pkg": "false",
    "keywords8.*.bnl;*.bnh": "BNL_KEYWORD7 BNL_KEYWORD8 BNL_KEYWORD9",
    "keywords8.*.exp": "",
    "keywords8.*.src;*.pkg": "",
    "lexer.*.bnl;*.bnh": "generic",
    "lexer.*.exp": "generic",
    "lexer.*.src;*.pkg": "generic"
}
```

---

## Validation rules & common errors
- **Missing `filenamePattern`** in a per-language JSON causes packing to fail; filenamePattern must be non-empty.
- **Invalid `isCaseSensitive`** (not exactly `"true"` or `"false"`) is rejected on pack/merge input.
- **Duplicate `filenamePattern`** among incoming per-language JSON files is rejected at pack time (the CLI refuses to create a blob with duplicate filenamePattern values in the same batch).
- **Merge conflict**: during merge, if an incoming language has a `filenamePattern` that already exists for a different UUID in the target blob, the tool fails and asks the user to resolve the conflict manually.
