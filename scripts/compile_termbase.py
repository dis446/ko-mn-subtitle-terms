#!/usr/bin/env python3
"""Compile the layered termbase into an LLM prompt block (and optionally TBX).

  compile_termbase.py --work the-remarried-empress --domains court-historical
  compile_termbase.py --work the-remarried-empress --domains court-historical --tbx out.tbx
  compile_termbase.py --work the-remarried-empress --strict   # exit 1 if anything needs_review

Precedence, highest first:  works/  >  domains/  >  rules/  >  global/

Only CONFIRMED entries are emitted into the prompt by default; needs_review
entries are listed separately as warnings, because shipping an unapproved
guess into a translation run is how a season ends up inconsistent.
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def yload(path):
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect(entry, out, layer, warnings):
    """Flatten a work/domain document into (ko -> record) pairs."""
    def add(ko, mn, en="", status="needs_review", note="", group=""):
        if not ko or not mn:
            return
        rec = {"ko": ko, "mn": mn, "en": en, "status": status,
               "note": note, "group": group, "layer": layer}
        prev = out.get(ko)
        # first writer wins — layers are applied in precedence order
        if prev is None:
            out[ko] = rec
            if status != "confirmed":
                warnings.append(f"[{layer}] {ko} → {mn} (needs_review)")

    for key, val in (entry or {}).items():
        if isinstance(val, list):
            for it in val:
                if isinstance(it, dict) and it.get("ko"):
                    add(it["ko"], it.get("chosen") or it.get("mn"),
                        it.get("en", ""), it.get("status", "needs_review"),
                        it.get("note", ""), key)
    return out


def load_global():
    path = os.path.join(ROOT, "global", "terms.yaml")
    if not os.path.exists(path):
        return {}
    return yload(path) or {}


def render_prompt(terms, rules_doc, work_title):
    lines = [f"# Terminology — {work_title}", "",
             "These renderings are MANDATORY. Use them exactly. "
             "Do not invent alternatives, do not re-transliterate names.", ""]
    groups = {}
    for rec in terms.values():
        groups.setdefault(rec["group"] or "terms", []).append(rec)
    order = ["characters", "places", "titles_royal", "nobility",
             "palace_household", "honorific_verbs", "overrides", "terms"]
    for g in order + [k for k in groups if k not in order]:
        if g not in groups:
            continue
        lines.append(f"## {g}")
        for rec in sorted(groups[g], key=lambda r: r["ko"]):
            tail = f"  ({rec['en']})" if rec["en"] else ""
            lines.append(f"- {rec['ko']} = {rec['mn']}{tail}")
        lines.append("")
    if rules_doc:
        r = rules_doc.get("rules", {})
        lines.append("## register rules")
        if (r.get("stop_voicing") or {}).get("enabled"):
            lines.append("- Korean plain stops: к/т/п word-initially, г/д/б between vowels.")
        lines.append("- Address royalty with honorific verbs (морилох, залах, соёрхох).")
        lines.append("- Never use bare чи to a noble or royal; use та + honorific.")
    return "\n".join(lines).rstrip() + "\n"


def to_tbx(terms, lang_src="ko", lang_tgt="mn"):
    """Minimal TBX-Basic export for CAT tools (ISO 30042)."""
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<tbx style="dca" type="TBX-Basic" xml:lang="en" '
           'xmlns="urn:iso:std:iso:30042:ed-2">',
           f'  <tbxHeader><fileDesc><sourceDesc><p>ko-mn-subtitle-terms</p>'
           f'</sourceDesc></fileDesc></tbxHeader>',
           '  <text><body>']
    for rec in sorted(terms.values(), key=lambda r: r["ko"]):
        out.append('    <termEntry>')
        out.append(f'      <langSet xml:lang="{lang_src}"><tig><term>{rec["ko"]}</term></tig></langSet>')
        out.append(f'      <langSet xml:lang="{lang_tgt}"><tig><term>{rec["mn"]}</term></tig></langSet>')
        if rec.get("note"):
            note = rec["note"].strip().replace("&", "&amp;").replace("<", "&lt;")
            out.append(f'      <descripGrp><descrip type="context">{note}</descrip></descripGrp>')
        out.append('    </termEntry>')
    out += ['  </body></text>', '</tbx>']
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, help="slug under works/ (no .yaml)")
    ap.add_argument("--domains", default="", help="comma-separated domain slugs")
    ap.add_argument("--include-unreviewed", action="store_true",
                    help="also emit needs_review entries into the prompt")
    ap.add_argument("--strict", action="store_true", help="exit 1 if anything needs_review")
    ap.add_argument("--tbx", metavar="PATH")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    warnings, terms = [], {}
    rules_doc = yload(os.path.join(ROOT, "rules", "hangul-to-cyrillic.yaml"))

    # precedence: works > domains > global
    work_path = os.path.join(ROOT, "works", a.work + ".yaml")
    if not os.path.exists(work_path):
        sys.exit(f"no such work: {work_path}")
    work = yload(work_path)
    collect(work, terms, "work", warnings)
    for d in [x.strip() for x in a.domains.split(",") if x.strip()]:
        p = os.path.join(ROOT, "domains", d + ".yaml")
        if not os.path.exists(p):
            sys.exit(f"no such domain: {p}")
        collect(yload(p), terms, f"domain:{d}", warnings)
    collect(load_global(), terms, "global", warnings)

    confirmed = {k: v for k, v in terms.items() if v["status"] == "confirmed"}
    pending = {k: v for k, v in terms.items() if v["status"] != "confirmed"}
    emit = dict(confirmed)
    if a.include_unreviewed:
        emit.update(pending)

    title = (work.get("work") or {}).get("title_en", a.work)
    prompt = render_prompt(emit, rules_doc, title)

    if a.tbx:
        open(a.tbx, "w", encoding="utf-8").write(to_tbx(emit))
        print(f"wrote {a.tbx}", file=sys.stderr)

    if a.json:
        print(json.dumps({"confirmed": len(confirmed), "pending": len(pending),
                          "emitted": len(emit), "warnings": warnings},
                         ensure_ascii=False, indent=1))
    else:
        sys.stdout.write(prompt)
        if pending and not a.include_unreviewed:
            print(f"\n# {len(pending)} entries withheld (needs_review):", file=sys.stderr)
            for w in warnings:
                print(f"#   {w}", file=sys.stderr)

    if a.strict and pending:
        sys.exit(1)


if __name__ == "__main__":
    main()
