from __future__ import annotations

import re
from datetime import date

from . import parser_llm, parser_offline as po

def parse(text: str | None, lang_hint: str | None = None, today: date | None = None,
          use_phrases: bool = True, allow_llm: bool = True) -> dict:
    transcript_norm, lang = po.normalize(text, lang_hint)
    if use_phrases and transcript_norm:
        item = po.lookup_phrase(transcript_norm)
        if item is not None:
            return po.from_phrase(item, transcript_norm, lang).to_dict()

    r = po.parse_rules(transcript_norm, lang, today)
    has_letters = bool(re.search(r"[^\W\d_]", transcript_norm))
    if allow_llm and has_letters and r.extracted_count < po.ACCEPT_MIN_FIELDS:
        got = parser_llm.llm_extract(transcript_norm)
        if got is not None:
            provider, raw = got
            c = parser_llm.convert(raw, transcript_norm, today)
            used = False
            for k in (*po.SIX_FIELDS, "payment_terms"):
                if r.fields.get(k) is not None or k in r.blocked:
                    continue
                if k in c.fields:
                    r.fields[k] = c.fields[k]
                    used = True
                    if k in c.computed:
                        r.computed.append(k)
                elif k in c.invalid and k not in r.missing_fields:
                    r.missing_fields.append(k)
                    r.blocked.append(k)
            if "max_price_t" in c.fields and r.fields.get("max_price_t") == c.fields["max_price_t"]:
                for x in c.confirm:
                    if x not in r.missing_fields:
                        r.missing_fields.append(x)
            if c.dropped:
                r.hints.append("llm_numbers_dropped")
            r.hints.extend(h for h in c.hints if h not in r.hints)
            if used:
                r.source = provider
    return po.finalize(r, today).to_dict()

def numbers_confirmed(result: dict) -> bool:
    nums = parser_llm.transcript_numbers(result["transcript_norm"])
    for k in ("qty_t", "max_price_t"):
        v = result["fields"].get(k)
        if v is None or k in result.get("computed", []):
            continue
        if not parser_llm._in_transcript(v, nums):
            return False
    return True
