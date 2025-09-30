#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Tuple, List

from pathvalidate import sanitize_filename

# Araxis key prefixes
K_FILE_PATTERNS = "file.patterns."
K_DESC = "genericlanguage.description."
K_KW1 = "keywords.*."
K_KW2 = "keywords2.*."
K_OPS = "keywords3.*."
K_SL = "keywords4.*."
K_ML_START = "keywords5.*."
K_ML_END = "keywords6.*."
K_CASE = "keywords7.*."
K_KW3 = "keywords8.*."
K_LEXER = "lexer.*."

# TODO: use fnmatch?
def pattern_to_key_suffix(filename_pattern: str) -> str:
    parts = filename_pattern.split(";")
    if parts:
        p0 = parts[0]
        if p0.startswith("*."):
            parts[0] = p0[2:]
        elif p0.startswith("*"):
            parts[0] = p0[1:]
    return ";".join(parts)

@dataclass
class Language:
    uuid: str
    name: str
    filenamePattern: str
    keywordsClass1: str = ""
    keywordsClass2: str = ""
    keywordsClass3: str = ""
    operatorSymbols: str = ""
    singleLineCommentSymbols: str = ""
    multiLineCommentStartSymbols: str = ""
    multiLineCommentEndSymbols: str = ""
    isCaseSensitive: str = "false"
    backslashIsAStringEscape: bool = True
    lexer: str = "generic"

    @staticmethod
    def from_flat(uuid: str, file_patterns: str, flat: Dict[str, str]) -> "Language":
        name = flat.get(K_DESC + uuid, "")
        fp = file_patterns
        # Helper to fetch keys using normalized suffix
        def get(k_prefix: str) -> str:
            return flat.get(k_prefix + pattern_to_key_suffix(fp), "")
        # Parse case sensitivity and backslash escape (keywords7)
        case_raw = get(K_CASE).strip()
        is_case = "false"
        backslash_escape = True
        if case_raw:
            parts = case_raw.split()
            if parts:
                val = parts[0].lower()
                if val in ("true", "false"):
                    is_case = val
            if "no_backslash_escape" in case_raw:
                backslash_escape = False
        return Language(
            uuid=uuid,
            name=name,
            filenamePattern=file_patterns,
            keywordsClass1=get(K_KW1),
            keywordsClass2=get(K_KW2),
            keywordsClass3=get(K_KW3),
            operatorSymbols=get(K_OPS),
            singleLineCommentSymbols=get(K_SL),
            multiLineCommentStartSymbols=get(K_ML_START),
            multiLineCommentEndSymbols=get(K_ML_END),
            isCaseSensitive=is_case,
            backslashIsAStringEscape=backslash_escape,
            lexer=get(K_LEXER) or "generic",
        )

def read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read()

def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(text)

def load_json_with_optional_header(path: Path) -> Dict[str, str]:
    raw = read_text(path)
    i = raw.find("{")
    data = json.loads(raw[i:] if i >= 0 else raw)
    if not isinstance(data, dict):
        raise SystemExit("Top-level JSON must be an object.")
    # Coerce to str->str
    out = {}
    for k, v in data.items():
        k = str(k)
        v = "" if v is None else str(v)
        out[k] = v
    return out

def dump_araxis_json(flat: Dict[str, str], outfile: Path, no_header: bool) -> None:
    if no_header:
        txt = json.dumps(flat, ensure_ascii=False, indent=2)
    else:
        txt = "json: " + json.dumps(flat, ensure_ascii=False, separators=(",", ":"))
    write_text(outfile, txt)

def parse_languages_from_flat(flat: Dict[str, str]) -> Tuple[Dict[str, Language], Dict[str, str]]:
    uuid_to_lang: Dict[str, Language] = {}
    pattern_to_uuid: Dict[str, str] = {}
    for k, v in flat.items():
        if k.startswith(K_FILE_PATTERNS):
            uuid = k[len(K_FILE_PATTERNS):]
            lang = Language.from_flat(uuid, v, flat)
            uuid_to_lang[uuid] = lang
            if lang.filenamePattern:
                pattern_to_uuid[lang.filenamePattern] = uuid
    return uuid_to_lang, pattern_to_uuid

def build_flat_from_languages(langs: List[Language]) -> Dict[str, str]:
    flat: Dict[str, str] = {}
    for L in langs:
        flat[K_FILE_PATTERNS + L.uuid] = L.filenamePattern
        flat[K_DESC + L.uuid] = L.name
        suffix = pattern_to_key_suffix(L.filenamePattern)
        flat[K_KW1 + suffix] = L.keywordsClass1
        flat[K_KW2 + suffix] = L.keywordsClass2
        flat[K_KW3 + suffix] = L.keywordsClass3
        flat[K_OPS + suffix] = L.operatorSymbols
        flat[K_SL + suffix] = L.singleLineCommentSymbols
        flat[K_ML_START + suffix] = L.multiLineCommentStartSymbols
        flat[K_ML_END + suffix] = L.multiLineCommentEndSymbols
        # Build keywords7 value: "<true|false>" optionally followed by " no_backslash_escape"
        case_val = (L.isCaseSensitive.lower().strip() if L.isCaseSensitive else "false")
        if L.backslashIsAStringEscape is False:
            flat[K_CASE + suffix] = f"{case_val} no_backslash_escape"
        else:
            flat[K_CASE + suffix] = case_val
        flat[K_LEXER + suffix] = L.lexer or "generic"
    return flat

def load_languages_from_dir(indir: Path) -> List[Language]:
    langs: List[Language] = []
    for p in sorted(indir.glob("*.json")):
        obj = json.loads(p.read_text(encoding="utf-8"))
        required = ["uuid", "name", "filenamePattern", "isCaseSensitive", "lexer"]
        for r in required:
            if r not in obj:
                raise SystemExit(f"Missing required field '{r}' in {p.name}")
        backslash = obj.get("backslashIsAStringEscape", True)
        # Allow JSON true/false or string forms
        if isinstance(backslash, str):
            backslash = backslash.lower() in ("true", "1", "yes")
        L = Language(
            uuid=str(obj.get("uuid","")),
            name=str(obj.get("name","")),
            filenamePattern=str(obj.get("filenamePattern","")),
            keywordsClass1=str(obj.get("keywordsClass1","")),
            keywordsClass2=str(obj.get("keywordsClass2","")),
            keywordsClass3=str(obj.get("keywordsClass3","")),
            operatorSymbols=str(obj.get("operatorSymbols","")),
            singleLineCommentSymbols=str(obj.get("singleLineCommentSymbols","")),
            multiLineCommentStartSymbols=str(obj.get("multiLineCommentStartSymbols","")),
            multiLineCommentEndSymbols=str(obj.get("multiLineCommentEndSymbols","")),
            isCaseSensitive=str(obj.get("isCaseSensitive","false")).lower(),
            backslashIsAStringEscape=bool(backslash),
            lexer=str(obj.get("lexer","generic")) or "generic",
        )
        if L.isCaseSensitive not in ("true","false"):
            raise SystemExit(f"isCaseSensitive must be 'true' or 'false' in {p.name}")
        if not L.filenamePattern:
            raise SystemExit(f"filenamePattern must be non-empty in {p.name}")
        langs.append(L)
    return langs

def cmd_unpack(args: argparse.Namespace) -> None:
    flat = load_json_with_optional_header(Path(args.input_file))
    uuid_to_lang, _ = parse_languages_from_flat(flat)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    used = set()
    for lang in uuid_to_lang.values():
        base = sanitize_filename(lang.name) or "unnamed"
        fname = base + ".json"
        if fname in used or (out_dir / fname).exists():
            suffix = "-" + re.sub(r"[^A-Za-z0-9]+", "", lang.uuid)[:8]
            fname = f"{base}{suffix}.json"
        used.add(fname)
        # Write the Language dataclass to disk, including backslashIsAStringEscape
        data = asdict(lang)
        write_text(out_dir / fname, json.dumps(data, ensure_ascii=False, indent=2))
    print(f"Wrote {len(uuid_to_lang)} language JSON file(s) to: {out_dir}")

def cmd_pack(args: argparse.Namespace) -> None:
    langs = load_languages_from_dir(Path(args.input_dir))
    # Ensure unique filenamePattern
    seen = {}
    for L in langs:
        if L.filenamePattern in seen and seen[L.filenamePattern] != L.uuid:
            raise SystemExit(f"Duplicate filenamePattern between UUIDs {seen[L.filenamePattern]} and {L.uuid}: '{L.filenamePattern}'")
        seen[L.filenamePattern] = L.uuid
    flat = build_flat_from_languages(langs)
    dump_araxis_json(flat, Path(args.output_file), args.no_header)
    print(f"Wrote Araxis JSON to: {args.output_file}")

def cmd_merge(args: argparse.Namespace) -> None:
    out_file = Path(args.output_file)
    target_flat = load_json_with_optional_header(out_file) if out_file.exists() else {}
    uuid_to_lang, pattern_to_uuid = parse_languages_from_flat(target_flat)
    incoming = load_languages_from_dir(Path(args.input_dir))

    def remove_lang(uuid: str) -> None:
        fp_old = target_flat.get(K_FILE_PATTERNS + uuid, "")
        for k in (K_FILE_PATTERNS + uuid, K_DESC + uuid):
            target_flat.pop(k, None)
        if fp_old:
            suffix = pattern_to_key_suffix(fp_old)
            for pref in (K_KW1, K_KW2, K_KW3, K_OPS, K_SL, K_ML_START, K_ML_END, K_CASE, K_LEXER):
                target_flat.pop(pref + suffix, None)

    for L in incoming:
        uuid_exists = L.uuid in uuid_to_lang
        conflict_uuid = pattern_to_uuid.get(L.filenamePattern)
        if (not uuid_exists) and conflict_uuid and conflict_uuid != L.uuid:
            raise SystemExit(
                "Merge conflict: filenamePattern already present for another language.\n"
                f"  Incoming UUID: {L.uuid}\n"
                f"  Conflicting UUID: {conflict_uuid}\n"
                f"  filenamePattern: '{L.filenamePattern}'"
            )
        if uuid_exists:
            remove_lang(L.uuid)
        uuid_to_lang[L.uuid] = L
        pattern_to_uuid[L.filenamePattern] = L.uuid

    flat_new = build_flat_from_languages(list(uuid_to_lang.values()))
    dump_araxis_json(flat_new, out_file, args.no_header)
    print(f"Merged {len(incoming)} language(s) into: {out_file}")

def main(argv: List[str]) -> None:
    p = argparse.ArgumentParser(description="Unpack/pack/merge Araxis Merge generic syntax definitions.")
    p.add_argument("--no-header", action="store_true", help="Omit 'json:' header and pretty-print with indent=2.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pu = sub.add_parser("unpack", help="Unpack Araxis JSON into per-language JSONs.")
    pu.add_argument("input_file")
    pu.add_argument("output_dir")
    pu.set_defaults(func=cmd_unpack)

    pp = sub.add_parser("pack", help="Pack per-language JSONs into Araxis JSON.")
    pp.add_argument("input_dir")
    pp.add_argument("output_file")
    pp.set_defaults(func=cmd_pack)

    pm = sub.add_parser("merge", help="UPSERT per-language JSONs into an existing Araxis JSON.")
    pm.add_argument("input_dir")
    pm.add_argument("output_file")
    pm.set_defaults(func=cmd_merge)

    args = p.parse_args(argv)
    args.func(args)

if __name__ == "__main__":
    main(sys.argv[1:])
