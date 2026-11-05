#!/usr/bin/env python3
"""Hangul → Mongolian Cyrillic transliteration engine.

Rule-based, not a name list: any modern Hangul syllable transliterates from
rules/hangul-to-cyrillic.yaml, so new shows need only exception entries.

  translit.py 나비에 소비에슈 라스타
  translit.py --name 김정은               # Korean personal name: Ким Жон Ун
  translit.py --test                      # run tests/corpus.yaml
  translit.py --explain 소비에슈           # show per-syllable derivation

Requires PyYAML (requirements.txt). v1 shipped a fallback parser whose
hard-coded rules silently disagreed with the YAML (it enabled liquid
assimilation), so it was removed: one source of truth.
"""
import argparse
import json
import os
import sys

import yaml

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
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def decompose(ch):
    code = ord(ch) - S_BASE
    if not (0 <= code <= S_LAST - S_BASE):
        return None
    return CHO[code // (N_JUNG * N_JONG)], JUNG[(code % (N_JUNG * N_JONG)) // N_JONG], JONG[code % N_JONG]


def _on(r, key):
    return bool((r.get(key) or {}).get("enabled", False))


def _pieces(text, rules, closed_codas=False):
    """Return a list of (piece, is_hangul) — one piece per input character.

    closed_codas: every syllable is written as its own word (name mode), so a
    coda always takes its word-final form even before a vowel-initial syllable.
    """
    ini, vow, fin = rules["initials"], rules["vowels"], rules["finals"]
    fin_v = rules.get("finals_before_vowel") or fin
    r = rules.get("rules", {})
    sv = r.get("stop_voicing") or {}
    sv_init, sv_else = sv.get("word_initial") or {}, sv.get("elsewhere") or {}
    tense = (r.get("tense_initial") or {}).get("map") or {}
    pal = r.get("palatalisation") or {}
    pal_trig, pal_map, pal_vow = set(pal.get("triggers") or []), pal.get("map") or {}, pal.get("vowel_map") or {}
    aff = r.get("affricate_glide_absorption") or {}
    aff_c, aff_vow = set(aff.get("consonants") or []), aff.get("vowel_map") or {}
    ep = r.get("epenthetic_eu") or {}
    euv = r.get("eu_vowel_initial") or {}
    uiv = r.get("ui_vowel") or {}

    sylls = [decompose(ch) for ch in text]
    n = len(sylls)
    out = []            # (piece, is_hangul)
    force_l = set()     # syllable indices whose onset ㄹ is the l of a Cl cluster

    def prev_out():
        return out[-1][0] if out and out[-1][1] else ""

    for idx, ch in enumerate(text):
        d = sylls[idx]
        if d is None:
            out.append((ch, False))
            continue
        c, v, j = d
        prev = sylls[idx - 1] if idx > 0 else None
        nxt = sylls[idx + 1] if idx + 1 < n else None
        word_initial = prev is None
        word_final = nxt is None

        # ── onset ──
        cons = ini.get(c, "")
        if _on(r, "tense_initial") and word_initial and c in tense:
            cons = tense[c]
        if _on(r, "stop_voicing") and c in sv_init:
            cons = sv_init[c] if word_initial else sv_else.get(c, cons)
        if c == "ㄹ" and (idx in force_l or prev_out().endswith("л")):
            cons = "л"

        # ── epenthetic ㅡ ──
        if _on(r, "cluster_eu_l") and v == "ㅡ" and c != "ㅇ" and j == "ㄹ" \
                and nxt is not None and nxt[0] == "ㄹ":
            out.append((cons, True))
            force_l.add(idx + 1)
            continue
        if _on(r, "epenthetic_eu") and v == "ㅡ" and c != "ㅇ" and j == "":
            if not word_initial or (ep.get("word_initial_if_followed") and not word_final):
                out.append((cons, True))
                continue

        # ── nucleus ──
        vv = vow.get(v, "")
        if v == "ㅡ" and c == "ㅇ" and _on(r, "eu_vowel_initial"):
            vv = euv.get("value", "у")
        if v == "ㅢ" and _on(r, "ui_vowel"):
            vv = uiv.get("vowel_initial", "уй") if c == "ㅇ" else uiv.get("after_consonant", "и")
        if _on(r, "palatalisation") and c in pal_map and v in pal_trig:
            cons = pal_map[c]
            vv = pal_vow.get(v, vv)
        if _on(r, "affricate_glide_absorption") and c in aff_c and v in aff_vow:
            vv = aff_vow[v]

        # ── coda ──
        if j and not closed_codas and not word_final and nxt[0] == "ㅇ":
            jj = fin_v.get(j, fin.get(j, ""))
        else:
            jj = fin.get(j, "")

        piece = cons + vv + jj
        if _on(r, "seam_i_e") and piece.startswith("э") and prev_out().endswith("и"):
            piece = "е" + piece[1:]
        out.append((piece, True))
    return out


def transliterate(text, rules, name=False):
    """Transliterate a Korean string to Mongolian Cyrillic.

    name=True: Korean personal name. Sound rules run across the whole name;
    output is one capitalised word per syllable (Mongolian usage).
    """
    pres = rules.get("presentation") or {}
    if name:
        parts = []
        for word in text.split():
            ps = [p for p, h in _pieces(word, rules, closed_codas=True)]
            parts += [p[:1].upper() + p[1:] for p in ps if p]
        return " ".join(parts)
    words = []
    for word in text.split(" "):
        s = "".join(p for p, _ in _pieces(word, rules))
        if pres.get("capitalise_first_letter", True) and s:
            s = s[0].upper() + s[1:]
        words.append(s)
    return " ".join(words)


def explain(text, rules):
    rows = []
    for (piece, h), ch in zip(_pieces(text, rules), text):
        d = decompose(ch)
        rows.append((ch, "—" if d is None else f"{d[0]}+{d[1]}+{d[2] or '∅'}", piece))
    return rows


def run_tests(rules, corpus_path=None):
    corpus_path = corpus_path or os.path.join(ROOT, "tests", "corpus.yaml")
    with open(corpus_path, encoding="utf-8") as f:
        cases = yaml.safe_load(f).get("cases", [])
    fails = 0
    for c in cases:
        got = transliterate(c["ko"], rules, name=c.get("mode") == "name")
        ok = got == c["mn"]
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {c['ko']:<12} expect={c['mn']:<16} got={got}"
              + ("" if ok else f"   [{c.get('note', '')}]"))
    print(f"\n{len(cases) - fails}/{len(cases)} passed")
    return 0 if fails == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="*")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--name", action="store_true", help="treat input as Korean personal names")
    ap.add_argument("--explain", metavar="KO")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rules = load_rules()

    if a.test:
        sys.exit(run_tests(rules))
    if a.explain:
        for ch, jamo, piece in explain(a.explain, rules):
            print(f"  {ch}  {jamo:<12} -> {piece}")
        print(f"  => {transliterate(a.explain, rules, name=a.name)}")
        return
    if not a.text:
        ap.error("give Korean text, --test, or --explain")
    res = [{"ko": t, "mn": transliterate(t, rules, name=a.name)} for t in a.text]
    print(json.dumps(res, ensure_ascii=False) if a.json
          else "\n".join(f"{r['ko']}\t{r['mn']}" for r in res))


if __name__ == "__main__":
    main()
