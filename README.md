# ko-mn-subtitle-terms

Terminology and transliteration rules for Korean → Mongolian Cyrillic subtitles.

## Why this exists

There is **no Mongolian national standard** for rendering foreign names and terms
into Cyrillic. The National Council on Language Policy (Ерөнхийлөгчийн дэргэдэх
Хэлний бодлогын үндэсний зөвлөл) stated this plainly in October 2025:

> "гадаад үг, нэр томьёо, оноосон нэрийг монгол хэлнээ буулгах тогтсон дүрэм,
> стандарт байхгүй" — *there is no established rule or standard for rendering
> foreign words, terms and proper names into Mongolian.*

MNS 5217:2012 is often mistaken for the answer. It is **Cyrillic → Latin
romanisation** (passports, maps) — the wrong direction entirely.

So every Korean→Mongolian subtitle project invents the same terms privately, and
every one of them spells `Sovieshu` differently. This repo is one attempt to stop
that: a deterministic, tested, versioned convention.

## What is here

```
rules/hangul-to-cyrillic.yaml   jamo-level transliteration rules (the core asset)
rules/honorifics.yaml           register policy
domains/court-historical.yaml   sageuk title pack (closed set of ~50 terms)
works/*.yaml                    per-title exceptions
scripts/translit.py             rule engine + test runner
scripts/compile_termbase.py     layer resolver -> LLM prompt block / TBX export
tests/corpus.yaml               regression corpus from real dialogue
```

## Precedence

```
works/  >  domains/  >  rules/  >  global/
```

A work-level entry always wins. That is what lets a single fix to `폐하`
propagate to every show, while one awkward character name stays local.

## The rule engine, not a name list

A name list does not scale — every new drama adds eight names and you are back to
guessing. This repo transliterates from **Hangul jamo**, so any modern syllable
maps deterministically and new shows need only exception entries.

```
$ python3 scripts/translit.py 라스타 소비에슈 코샤르
라스타	Раста
소비에슈	Собиешу
코샤르	Кошар

$ python3 scripts/translit.py --explain 소비에슈
$ python3 scripts/translit.py --test
18/18 passed
```

Every rule in the file is backed by a case in `tests/corpus.yaml`, mined from
real subtitle tracks. Change a rule, and a broken name fails the build.

## Status discipline

Every entry is marked:

- `confirmed` — validated in a multi-model bake-off against real dialogue, or
  approved by a native speaker
- `needs_review` — drafted, **not approved**

`compile_termbase.py` emits only `confirmed` entries into a prompt by default and
lists the rest as warnings. Shipping an unapproved guess into a translation run is
how a season ends up inconsistent — so the default is to withhold, and `--strict`
fails the build if anything is pending.

```
$ python3 scripts/compile_termbase.py --work the-remarried-empress \
      --domains court-historical
$ python3 scripts/compile_termbase.py ... --tbx terms.tbx     # CAT-tool interop
```

TBX export is [TBX-Basic](https://tbxinfo.net/) (ISO 30042), usable in OmegaT,
memoQ and Trados.

## Contributing

The highest-value contribution is **resolving a `needs_review` entry** — those
are the places where the rule output and convention disagree, and only a native
speaker can settle them. Bring a reason, not a preference.

Add a `tests/corpus.yaml` case with any new rule.

## Licence

- **Code and rules:** MIT
- **Terminology data:** CC BY-SA 4.0

No subtitle text belongs in this repo. Terms and rules are facts and conventions;
dialogue is not ours to redistribute.
