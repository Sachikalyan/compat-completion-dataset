# Provenance

| item | value |
|---|---|
| Upstream source | https://github.com/mdn/browser-compat-data (npm `@mdn/browser-compat-data`) |
| Upstream version | 8.1.3, data timestamp 2026-09-24T13:25:51Z |
| Upstream licence | CC0 1.0 Universal (`LICENSE`) |
| Download | registry.npmjs.org tarball, 2026-10-01, kept unmodified in `raw/` |
| Derivation | `prepare.py`, seed 20261001, Python standard library, deterministic |
| Derived licence | CC0 1.0 Universal |

## Transformations
1. Categories kept: api, css, html, http, javascript, mathml, svg, webassembly, webdriver (webextensions, manifests, mediatypes excluded). Browsers kept: 13 web browsers (ie, nodejs, deno, bun excluded).
2. Target normalisation per (feature, browser): first support entry; `false`/absent/`preview`/flagged → `false`; version-unknown (`true`) or undated versions → cell dropped; `≤N` → `N`. Features with fewer than six usable cells dropped (20,647 → 18,517).
3. Anonymisation: feature names and paths removed; ids assigned by seeded shuffle; hierarchy (`parent_id`), depth, category and status flags kept.
4. Split: `mathml` and `webassembly` entirely test; 20 % of level-3 subtrees test (2,212 of 11,058); 14,394 train / 4,123 test features.
5. Reveal regimes: derivative1, source1, random2, lineage_pair, engine_webkit (train, labelled, and test) and engine_blink, subtree_engine (test only); hidden cells removed from `test_support.csv` and recorded as `target` in `answers.csv`, keyed by `id`, with regime/hard/unseen-category/date in one `meta` column.

No personal data are contained in the derived files.
