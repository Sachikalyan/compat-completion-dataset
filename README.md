# Compat Completion: Browser Support Table with Hidden Cells (18,517 anonymised web-platform features)

**Platform upload:** `compat_completion_dataset.zip` in this repository is the exact file registered on the challenge platform (9 CSV files, flat; sha256 `707dadb5236fd762846c609ddb83510f9b22d2696e44f3708d27bf4ea0f00de4`). The same nine CSVs are also checked in individually at the repository root, with per-file checksums in `SHA256SUMS`.

Browser support table of the web platform with hidden cells — 18,517 anonymised features × 13 browsers, seven reveal regimes, a private answer key. Released under CC0 1.0 (LICENSE). This repository is the canonical public home of the dataset; file checksums are in `SHA256SUMS`.

## Provenance and regeneration
Derived from the npm package `@mdn/browser-compat-data` 8.1.3 (CC0-1.0, https://github.com/mdn/browser-compat-data, data timestamp 2026-09-24), an unmodified copy of which is kept in `raw/browser-compat-data-8.1.3.tgz`. Regenerate byte-identically with

```
python prepare.py --raw raw/browser-compat-data-8.1.3.tgz --out data --seed 20261001
```

`prepare.py` needs only the Python standard library and runs in about four seconds. `answers.csv` is the private answer key and must not be exposed to challenge solvers; given this repository (or its ZIP) `prepare.py` separates it from the public files and checks their integrity.


## Overview
A structured-imputation dataset built from the browser-compatibility table of the web platform. Each of 18,517 **features** (CSS properties, DOM APIs, HTML/SVG/MathML elements and attributes, HTTP headers, JavaScript built-ins, WebAssembly and WebDriver capabilities) has, for each of 13 browsers, a `version_added` entry: the release version in which the browser first shipped the feature, or `false` if it never shipped. Feature names and paths are removed; each feature keeps its position in the hierarchy (`parent_id`), its depth, its category and its standardisation status. The browsers' complete release calendars (version, date, engine, upstream) are included. A regime-specific subset of cells has been **hidden** in the test split; the task supported by the dataset is to reconstruct those cells — with calibrated abstention — from lineage (derivative ↔ upstream browsers), hierarchy (sub-features ship with their parents), cross-engine regularities and release timelines.

Derived deterministically (seed 20261001, Python standard library, 4 s) from the CC0-1.0 npm package `@mdn/browser-compat-data` 8.1.3 (data timestamp 2026-09-24). Seven reveal regimes are applied (five present in training with labels; two harder compositions test-only). Two categories (`mathml`, `webassembly`) and 20 % of level-3 feature subtrees appear only in the test split.

## File Structure
All 9 files are flat CSVs with a header row and **no missing values**; feature tables join on `feature_id`, query tables on `id`.
- `browsers.csv` — 1,314 rows: every dated release of the 13 browsers
- `train_features.csv` — 14,394 rows: training features with hierarchy, category, status flags and the simulated reveal `regime`
- `train_support.csv` — 187,068 rows: every (feature, browser) cell of the training features
- `train_hidden.csv` — 25,882 rows: the cells that the training feature's regime would hide
- `test_features.csv` — 4,123 rows: test features (no regime column)
- `test_support.csv` — 40,937 rows: the visible cells of the test features
- `test_queries.csv` — 12,645 rows: the hidden cells to predict
- `sample_submission.csv` — 12,645 rows: valid trivial submission (`false`, never certain)
- `answers.csv` — 12,645 rows: private answer key (must not be exposed to solvers)

## Features

### `browsers.csv`
| Column | Type | Description |
|--------|------|-------------|
| `browser` | string | one of chrome, chrome_android, edge, firefox, firefox_android, oculus, opera, opera_android, safari, safari_ios, samsunginternet_android, webview_android, webview_ios |
| `version` | string | release version label, e.g. `57`, `13.1`, `9.4` |
| `release_date` | string (YYYY-MM-DD) | release date |
| `engine` | string | rendering engine: Blink, WebKit, Gecko, EdgeHTML, Presto, unknown |
| `engine_version` | string | engine and its version as one label, e.g. `Blink 81`, `WebKit 605.1.15` (`unknown` where the source has none) — for Blink derivatives this is the Chromium version |
| `status` | string | `retired`, `current`, `beta`, `nightly`, `planned`, `esr` |
| `upstream` | string | the browser this one derives from, or `none` |
| `type` | string | `desktop`, `mobile`, `xr` |

### `train_features.csv` / `test_features.csv`
| Column | Type | Description |
|--------|------|-------------|
| `feature_id` | string | `Fnnnnn`, assigned by a seeded shuffle (carries no information) |
| `parent_id` | string | the enclosing feature's id, or the category name for top-level features |
| `category` | string | api, css, html, http, javascript, mathml, svg, webassembly, webdriver |
| `depth` | int | number of path segments in the original feature path (2–8) |
| `experimental`, `standard_track`, `deprecated` | string {yes, no, unknown} | standardisation status flags |
| `regime` | string (train only) | derivative1, source1, random2, lineage_pair, engine_webkit — the reveal mechanism simulated for this feature |

### `train_support.csv` / `test_support.csv`
| Column | Type | Description |
|--------|------|-------------|
| `feature_id`, `browser` | string | cell coordinates |
| `version_added` | string | a release version of that browser (present in `browsers.csv`) or `false` |

### `train_hidden.csv` / `test_queries.csv`
| Column | Type | Description |
|--------|------|-------------|
| `id` | string (`test_queries` only) | `Qnnnnnn`, query identifier |
| `feature_id`, `browser` | string | the hidden cell |

### `sample_submission.csv`
| Column | Type | Description |
|--------|------|-------------|
| `id` | string | one row per query |
| `prediction` | string | a release version of the query's browser, or `false` (sample: `false`) |
| `certain` | int {0,1} | commitment flag (sample: 0) |

### `answers.csv` (private)
| Column | Type | Description |
|--------|------|-------------|
| `id` | string | query identifier |
| `target` | string | the true `version_added`: a release version or `false` |
| `feature_id`, `browser` | string | the hidden cell |
| `regime` | string | one of the seven regimes (incl. test-only engine_blink, subtree_engine) |
| `hard`, `unseen_category` | string {yes, no} | test-only regime / category absent from training |
| `target_date` | string | release date of the target version, or `none` |

## Characteristics
- 15.6 % of hidden cells are `false`; the rest are versions spanning 2008–2026.
- Blink derivatives follow Chrome with time-varying offsets; Safari iOS / WebView iOS follow Safari; Firefox Android follows Firefox. Samsung Internet version numbers are decoupled from Chromium's.
- 31 % of test features have a training feature as parent, 49 % a test feature.
- Audits: no train/test feature overlap; `false` share flat across id quintiles; ids and row order uninformative.
- Cells recorded upstream as version-unknown, preview-only or flag-gated were mapped to `false` or dropped; `≤N` versions were mapped to `N`.
- No personal data.