#!/usr/bin/env python3
"""Hangul → Mongolian Cyrillic transliteration engine.

Rule-based, not a name list: any modern Hangul syllable transliterates from
rules/hangul-to-cyrillic.yaml, so new shows need only exception entries.

  translit.py 나비에 소비에슈 라스타
  translit.py --test                      # run tests/corpus.yaml
  translit.py --explain 소비에슈           # show per-syllable derivation

stdlib only. PyYAML is used when available; a minimal fallback parser handles
the flat maps in the rule file so the tool runs on a bare python3.
"""
import argparse
import json
import os
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RULES = os.path.join(ROOT, "rules", "hangul-to-cyrillic.yaml")

S_BASE = 0xAC00
S_LAST = 0xD7A3
N_JUNG, N_JONG = 21, 28

CHO = ["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ",
       "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
JUNG = ["ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ", "ㅙ",
        "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ"]
JONG = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ",
        "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ",
        "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]


def load_rules(path=RULES):
    """Load the rule file. PyYAML if present, else a small purpose-built parser."""
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        pass
    # fallback: parse only the four flat sections this engine needs
    out = {"initials": {}, "vowels": {}, "finals": {}, "rules": {}}
    section = None
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            section = line[:-1]
            continue
        if section in ("initials", "vowels", "finals") and line.startswith("  "):
            k, _, v = line.strip().partition(":")
            v = v.split("#")[0].strip()
            if v in ('""', "''"):
                v = ""
            out[section][k.strip().strip('"')] = v.strip('"').strip("'")
    out["rules"] = {"palatalisation": {"enabled": True,
                                       "triggers": ["ㅑ", "ㅕ", "ㅛ", "ㅠ", "ㅣ"],
                                       "map": {"ㅅ": "ш", "ㅆ": "щ"}},
                    "epenthetic_eu": {"enabled": True},
                    "liquid_assimilation": {"enabled": True,
                                            "pairs": [["ㄴ", "ㄹ"], ["ㄹ", "ㄹ"]],
                                            "result": "лл"}}
    return out


def decompose(ch):
    code = ord(ch) - S_BASE
    if not (0 <= code <= S_LAST - S_BASE):
        return None
    return CHO[code // (N_JUNG * N_JONG)], JUNG[(code % (N_JUNG * N_JONG)) // N_JONG], JONG[code % N_JONG]


def transliterate(text, rules):
    """Transliterate a Korean string to Mongolian Cyrillic."""
    ini, vow, fin = rules["initials"], rules["vowels"], rules["finals"]
    r = rules.get("rules", {})
    pal = r.get("palatalisation") or {}
    pal_on = pal.get("enabled", False)
    pal_trig = set(pal.get("triggers") or [])
    pal_map = pal.get("map") or {}
    pal_vow = pal.get("vowel_map") or {}
    ep = (r.get("epenthetic_eu") or {}).get("enabled", False)
    la = r.get("liquid_assimilation") or {}
    la_on = la.get("enabled", False)
    la_pairs = {tuple(p) for p in (la.get("pairs") or [])}
    la_res = la.get("result", "лл")

    sylls = []
    for ch in text:
        d = decompose(ch)
        if d is None:
            sylls.append((None, ch))
        else:
            sylls.append((d, ch))

    sv = r.get("stop_voicing") or {}
    sv_on = sv.get("enabled", False)
    sv_init = sv.get("word_initial") or {}
    sv_med = sv.get("intervocalic") or {}

    out = []
    SONORANT = {"", "ㄴ", "ㅁ", "ㄹ", "ㅇ"}
    for idx, (d, ch) in enumerate(sylls):
        if d is None:
            out.append(ch)
            continue
        c, v, j = d
        # liquid assimilation across the boundary (final of prev + initial of this)
        if la_on and idx > 0 and out:
            prev = sylls[idx - 1][0]
            if prev and (prev[2], c) in la_pairs:
                if out[-1].endswith("ль"):
                    out[-1] = out[-1][:-2]
                out.append(la_res + vow.get(v, ""))
                # a final on this syllable still applies below
                if j:
                    out[-1] = out[-1] + fin.get(j, "")
                continue
        # epenthetic ㅡ: only a vowel carrier for a bare consonant. If the
        # syllable has its own final (근, 은, 틀) the ㅡ is a real vowel.
        if ep and v == "ㅡ" and c != "ㅇ" and idx > 0 and j == "":
            out.append(ini.get(c, ""))
            continue
        cons = ini.get(c, "")
        # stop voicing: Korean voices a plain stop only between voiced sounds,
        # so medial ㄱ/ㄷ/ㅂ become г/д/б after a vowel or sonorant, and stay
        # к/т/п after an obstruent (박근혜 → Пак Кын Хе, not Паггынхе).
        if sv_on and c in sv_init:
            prev_final = sylls[idx - 1][0][2] if idx > 0 and sylls[idx - 1][0] else ""
            if idx == 0 or prev_final not in SONORANT:
                cons = sv_init[c]
            else:
                cons = sv_med.get(c, cons)
        # initial ㄹ after a syllable already ending in л stays л (부틀린 → Бутлин)
        if c == "ㄹ" and idx > 0 and out and out[-1].endswith("л"):
            cons = "л"
        vv = vow.get(v, "")
        if pal_on and c in pal_map and v in pal_trig:
            cons = pal_map[c]
            vv = pal_vow.get(v, vv)
        jj = fin.get(j, "")
        pres = rules.get("presentation") or {}
        # word-final ㄹ softens: 김철 → Ким Чхоль
        if j == "ㄹ" and pres.get("word_final_l_soft", True) and idx == len(sylls) - 1:
            jj = "ль"
        # word-final ㄱ is written к, not г: 박 → Пак
        if j == "ㄱ" and idx == len(sylls) - 1:
            jj = "к"
        # A final obstruent is released as voiceless before a consonant and
        # voiced (liaison) only before a vowel-initial syllable:
        #   박근혜 → Паккынхе (ㄱ before ㄱ)   한국어 → Хангуго (ㄱ before ㅇ)
        if j in ("ㄱ", "ㄷ", "ㅂ") and idx < len(sylls) - 1:
            nxt = sylls[idx + 1][0]
            if nxt and nxt[0] != "ㅇ":
                jj = {"ㄱ": "к", "ㄷ": "т", "ㅂ": "п"}[j]
        piece = cons + vv + jj
        # и + э at a syllable seam reads as ие, not иэ
        if out and piece.startswith("э") and out[-1].endswith("и"):
            piece = "е" + piece[1:]
        out.append(piece)

    s = "".join(out)
    if (rules.get("presentation") or {}).get("capitalise_first_letter", True) and s:
        s = s[0].upper() + s[1:]
    return s


def explain(text, rules):
    rows = []
    for ch in text:
        d = decompose(ch)
        if d is None:
            rows.append((ch, "—", "—", "literal"))
            continue
        c, v, j = d
        rows.append((ch, f"{c}+{v}+{j or '∅'}",
                     rules["initials"].get(c, "") + rules["vowels"].get(v, "") + rules["finals"].get(j, ""),
                     ""))
    return rows


def run_tests(rules, corpus_path=None):
    corpus_path = corpus_path or os.path.join(ROOT, "tests", "corpus.yaml")
    raw = open(corpus_path, encoding="utf-8").read()
    cases, fails = [], 0
    try:
        import yaml
        cases = yaml.safe_load(raw).get("cases", [])
    except ImportError:
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" in line and not line.startswith("-"):
                continue
            if line.startswith("- "):
                line = line[2:]
            k, _, v = line.partition(":")
            if k.strip() and v.strip():
                cases.append({"ko": k.strip().strip('"'), "mn": v.strip().strip('"')})
    for c in cases:
        got = transliterate(c["ko"], rules)
        ok = got == c["mn"]
        if not ok:
            fails += 1
        print(f"{'PASS' if ok else 'FAIL'}  {c['ko']:<12} expect={c['mn']:<14} got={got}"
              + ("" if ok else f"   [{c.get('note','')}]"))
    print(f"\n{len(cases)-fails}/{len(cases)} passed")
    return 0 if fails == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="*")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--explain", metavar="KO")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rules = load_rules()

    if a.test:
        sys.exit(run_tests(rules))
    if a.explain:
        for ch, jamo, naive, note in explain(a.explain, rules):
            print(f"  {ch}  {jamo:<12} naive={naive:<6} {note}")
        print(f"  => {transliterate(a.explain, rules)}")
        return
    if not a.text:
        ap.error("give Korean text, --test, or --explain")
    res = [{"ko": t, "mn": transliterate(t, rules)} for t in a.text]
    print(json.dumps(res, ensure_ascii=False) if a.json
          else "\n".join(f"{r['ko']}\t{r['mn']}" for r in res))


if __name__ == "__main__":
    main()
