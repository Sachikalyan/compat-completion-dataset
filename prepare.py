#!/usr/bin/env python3
"""Compat Completion — preparation script.

Deterministically converts the @mdn/browser-compat-data npm tarball (CC0-1.0) into the
challenge's public / private files, OR (if given the already-prepared dataset) separates the
public files from the private answer key and verifies integrity (pass-through mode).

    python prepare.py --raw raw/browser-compat-data-8.1.3.tgz --out data --seed 20261001
    python prepare.py --raw <prepared_zip_or_dir> --out data

Outputs (all CSVs are blank-free; flags are yes/no strings; ids are order-free):
    public/browsers.csv           browser, version, release_date, engine, engine_version, status, upstream, type
    public/train_features.csv     feature_id, parent_id, category, depth, experimental, standard_track, deprecated, regime
    public/train_support.csv      feature_id, browser, version_added          (every cell of every training feature)
    public/train_hidden.csv       feature_id, browser                         (cells the training regime would hide)
    public/test_features.csv      feature_id, parent_id, category, depth, experimental, standard_track, deprecated
    public/test_support.csv       feature_id, browser, version_added          (visible cells only)
    public/test_queries.csv       id, feature_id, browser                     (hidden cells to predict)
    public/sample_submission.csv  id, prediction, certain
    private/answers.csv           id, target, feature_id, browser, regime, hard, unseen_category, target_date
    private/feature_manifest.csv  feature_id -> real BCD path (reviewer only)
    private/prepare_report.json
"""
import argparse, csv, hashlib, io, json, os, random, re, tarfile, zipfile
from collections import defaultdict

BROWSERS = ["chrome", "chrome_android", "edge", "firefox", "firefox_android", "oculus", "opera",
            "opera_android", "safari", "safari_ios", "samsunginternet_android", "webview_android", "webview_ios"]
SOURCES = ["chrome", "firefox", "safari"]
FAMILY = {"blink": ["chrome", "chrome_android", "edge", "opera", "opera_android", "samsunginternet_android",
                    "webview_android", "oculus"],
          "gecko": ["firefox", "firefox_android"],
          "webkit": ["safari", "safari_ios", "webview_ios"]}
DERIVS = {"chrome": ["chrome_android", "edge", "opera", "opera_android", "samsunginternet_android",
                     "webview_android", "oculus"],
          "firefox": ["firefox_android"], "safari": ["safari_ios", "webview_ios"]}
CATEGORIES = ["api", "css", "html", "http", "javascript", "mathml", "svg", "webassembly", "webdriver"]
UNSEEN_CATEGORIES = {"mathml", "webassembly"}          # whole categories held out in test
TRAIN_REGIMES = ["derivative1", "source1", "random2", "lineage_pair", "engine_webkit"]
HARD_REGIMES = ["engine_blink", "subtree_engine"]      # test-only compositions
TEST_SUBTREE_FRAC = 0.20                                # share of level-3 subtrees held out


# --------------------------------------------------------------------------- raw loading
def load_raw(raw):
    if os.path.isdir(raw):
        for root, _, files in os.walk(raw):
            if "data.json" in files:
                return json.load(open(os.path.join(root, "data.json"), encoding="utf-8"))
        raise SystemExit("data.json not found under %s" % raw)
    with tarfile.open(raw, "r:gz") as t:
        for m in t.getmembers():
            if m.name.endswith("data.json"):
                return json.load(io.TextIOWrapper(t.extractfile(m), encoding="utf-8"))
    raise SystemExit("data.json not found in %s" % raw)


def normalise(entry):
    """Support entry (dict or list) -> target string: a release version, or 'false'."""
    e = entry[0] if isinstance(entry, list) else entry
    va = e.get("version_added")
    if va is None or va is False or va is True or va == "preview":
        return "false" if va is not True else "true"
    if e.get("flags"):
        return "false"
    return va[1:] if va.startswith("≤") else va


def walk(node, path, out):
    if isinstance(node, dict):
        if "__compat" in node:
            out.append((path, node["__compat"]))
        for k, v in node.items():
            if k != "__compat":
                walk(v, path + [k], out)


def yn(v):
    return "unknown" if v is None else ("yes" if v else "no")


# --------------------------------------------------------------------------- pass-through
PUBLIC = ["browsers.csv", "train_features.csv", "train_support.csv", "train_hidden.csv", "test_features.csv",
          "test_support.csv", "test_queries.csv", "sample_submission.csv"]
PRIVATE = ["answers.csv"]
OPTIONAL_PRIVATE = ["feature_manifest.csv", "prepare_report.json"]


def _find_prepared(raw):
    if os.path.isdir(raw):
        for root, _, files in os.walk(raw):
            if "answers.csv" in files and "test_queries.csv" in files:
                return "dir", root
        return None
    try:
        with zipfile.ZipFile(raw) as z:
            names = z.namelist()
    except (zipfile.BadZipFile, IsADirectoryError):
        return None
    for n in names:
        if n.endswith("answers.csv") and n[:-len("answers.csv")] + "test_queries.csv" in names:
            return "zip", n[:-len("answers.csv")]
    return None


def split_prepared(raw, out):
    kind, root = _find_prepared(raw)
    pub, prv = os.path.join(out, "public"), os.path.join(out, "private")
    os.makedirs(pub, exist_ok=True); os.makedirs(prv, exist_ok=True)

    def read(name):
        if kind == "dir":
            p = os.path.join(root, name)
            return open(p, "rb").read() if os.path.exists(p) else None
        with zipfile.ZipFile(raw) as z:
            try:
                return z.read(root + name)
            except KeyError:
                return None
    for name in PUBLIC + PRIVATE:
        b = read(name)
        if b is None:
            raise SystemExit("prepared dataset is missing %s" % name)
        open(os.path.join(pub if name in PUBLIC else prv, name), "wb").write(b)
    for name in OPTIONAL_PRIVATE:
        b = read(name)
        if b is not None:
            open(os.path.join(prv, name), "wb").write(b)
    verify(pub, prv)


def verify(pub, prv):
    def rows(p):
        return list(csv.DictReader(open(p, newline="", encoding="utf-8")))
    q = rows(os.path.join(pub, "test_queries.csv")); a = rows(os.path.join(prv, "answers.csv"))
    s = rows(os.path.join(pub, "sample_submission.csv")); vis = rows(os.path.join(pub, "test_support.csv"))
    qid = {r["id"] for r in q}
    if not (qid == {r["id"] for r in a} == {r["id"] for r in s}):
        raise SystemExit("id mismatch between test_queries, answers and sample_submission")
    if len(qid) != len(q):
        raise SystemExit("duplicate query ids")
    qcells = {(r["feature_id"], r["browser"]) for r in q}
    vcells = {(r["feature_id"], r["browser"]) for r in vis}
    if qcells & vcells:
        raise SystemExit("leak: %d hidden cells are present in test_support.csv" % len(qcells & vcells))
    for name in PUBLIC + PRIVATE:
        for r in rows(os.path.join(pub if name in PUBLIC else prv, name)):
            if any(v == "" for v in r.values()):
                raise SystemExit("%s contains an empty cell" % name)
    print("verified: %d public files, %d private file(s), %d hidden cells, no leak, no empty cells"
          % (len(PUBLIC), len(PRIVATE), len(qid)))


# --------------------------------------------------------------------------- main pipeline
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=20261001)
    args = ap.parse_args()
    if _find_prepared(args.raw):
        return split_prepared(args.raw, args.out)

    rng = random.Random(args.seed)
    d = load_raw(args.raw)
    meta = d.get("__meta", {})

    # ---- browsers / releases
    browsers_rows, dates = [], {}
    for b in BROWSERS:
        info = d["browsers"][b]
        for ver, rel in info["releases"].items():
            rd = rel.get("release_date")
            if not rd:
                continue
            dates[(b, ver)] = rd
            eng = rel.get("engine") or "unknown"
            # engine_version is written as "<engine> <version>" so that it is a categorical string
            # (bare engine versions parse as numbers and look like heavy-tailed outliers to profilers)
            ev = "%s %s" % (eng, rel.get("engine_version")) if rel.get("engine_version") else "unknown"
            browsers_rows.append([b, ver, rd, eng, ev,
                                  rel.get("status") or "unknown", info.get("upstream") or "none", info.get("type") or "unknown"])
    browsers_rows.sort(key=lambda r: (r[0], r[2], r[1]))

    # ---- features
    feats = []
    for cat in CATEGORIES:
        walk(d[cat], [cat], feats)
    cells = {}       # path -> {browser: target}
    status = {}
    for path, comp in feats:
        key = ".".join(path)
        sup = comp.get("support", {})
        row = {}
        for b in BROWSERS:
            if b in sup:
                t = normalise(sup[b])
                if t == "true":                       # version unknown: unusable as a target -> drop cell
                    continue
                if t != "false" and (b, t) not in dates:   # version not in dated release table -> drop cell
                    continue
                row[b] = t
        if len(row) < 6:
            continue
        cells[key] = row
        st = comp.get("status") or {}
        status[key] = (yn(st.get("experimental")), yn(st.get("standard_track")), yn(st.get("deprecated")))
    paths = sorted(cells)
    parent_of = {}
    for p in paths:
        parts = p.split(".")
        par = None
        for k in range(len(parts) - 1, 0, -1):
            cand = ".".join(parts[:k])
            if cand in cells:
                par = cand; break
        parent_of[p] = par or parts[0]          # category name if no ancestor feature exists

    # ---- split: unseen categories + 20 % of level-3 subtrees -> test
    l3 = defaultdict(list)
    for p in paths:
        l3[".".join(p.split(".")[:3])].append(p)
    l3_keys = sorted(l3)
    rng.shuffle(l3_keys)
    test_l3 = set(l3_keys[: int(round(TEST_SUBTREE_FRAC * len(l3_keys)))])
    test_paths = [p for p in paths if p.split(".")[0] in UNSEEN_CATEGORIES or ".".join(p.split(".")[:3]) in test_l3]
    train_paths = [p for p in paths if p not in set(test_paths)]

    # ---- anonymised ids (seeded shuffle, order-free)
    perm = paths[:]
    rng.shuffle(perm)
    fid = {p: "F%05d" % (i + 1) for i, p in enumerate(perm)}
    def pid(p):
        par = parent_of[p]
        return fid[par] if par in fid else par

    children = defaultdict(list)
    for p in paths:
        if parent_of[p] in fid:
            children[parent_of[p]].append(p)

    def descendants(p):
        out = []
        stack = list(children[p])
        while stack:
            c = stack.pop(); out.append(c); stack.extend(children[c])
        return out

    # ---- regime assignment and hidden-cell selection
    def hide_for(regime, p, rng):
        row = cells[p]; present = [b for b in BROWSERS if b in row]
        if regime == "derivative1":
            opts = [b for b in present if b not in SOURCES]
        elif regime == "source1":
            opts = [b for b in present if b in SOURCES]
        elif regime == "random2":
            return rng.sample(present, min(2, len(present)))
        elif regime == "lineage_pair":
            opts = [s for s in SOURCES if s in present and any(dv in present for dv in DERIVS[s])]
            if not opts:
                return rng.sample(present, min(2, len(present)))
            s = rng.choice(opts)
            return [s, rng.choice([dv for dv in DERIVS[s] if dv in present])]
        elif regime == "engine_webkit":
            return [b for b in FAMILY["webkit"] if b in present]
        elif regime == "engine_blink":
            return [b for b in FAMILY["blink"] if b in present]
        else:
            raise ValueError(regime)
        return [rng.choice(opts)] if opts else [rng.choice(present)]

    train_regime, train_hidden = {}, {}
    for p in train_paths:
        r = rng.choice(TRAIN_REGIMES)
        train_regime[p] = r
        train_hidden[p] = hide_for(r, p, rng)

    test_regime, test_hidden = {}, {}
    test_set = set(test_paths)
    # subtree_engine: hide one whole engine family across a subtree root and all its test descendants
    roots = [p for p in test_paths if len([c for c in descendants(p) if c in test_set]) >= 2]
    rng.shuffle(roots)
    claimed = set()
    target_rows = len(test_paths) // 7          # about one regime's share of features
    for p in roots:
        group = [p] + [c for c in descendants(p) if c in test_set]
        if any(g in claimed for g in group):
            continue
        fam = rng.choice(["gecko", "webkit", "blink"])
        for g in group:
            hb = [b for b in FAMILY[fam] if b in cells[g]]
            if hb:
                test_regime[g] = "subtree_engine"; test_hidden[g] = hb; claimed.add(g)
        if len(claimed) >= target_rows:
            break
    remaining = [p for p in test_paths if p not in test_regime]
    rng.shuffle(remaining)
    all_test_regimes = TRAIN_REGIMES + ["engine_blink"]
    for i, p in enumerate(remaining):
        r = all_test_regimes[i % len(all_test_regimes)]
        test_regime[p] = r
        test_hidden[p] = hide_for(r, p, rng)

    # ---- assemble tables
    def feat_row(p, with_regime):
        st = status[p]
        r = [fid[p], pid(p), p.split(".")[0], len(p.split(".")), st[0], st[1], st[2]]
        if with_regime:
            r.append(train_regime[p])
        return r
    train_features = sorted((feat_row(p, True) for p in train_paths), key=lambda r: r[0])
    test_features = sorted((feat_row(p, False) for p in test_paths), key=lambda r: r[0])
    train_support = sorted([[fid[p], b, cells[p][b]] for p in train_paths for b in BROWSERS if b in cells[p]])
    train_hidden_rows = sorted([[fid[p], b] for p in train_paths for b in train_hidden[p]])
    test_support = sorted([[fid[p], b, cells[p][b]] for p in test_paths for b in BROWSERS
                           if b in cells[p] and b not in test_hidden[p]])
    queries = [(p, b) for p in test_paths for b in test_hidden[p]]
    rng.shuffle(queries)
    qid = {q: "Q%06d" % (i + 1) for i, q in enumerate(queries)}
    test_queries = sorted([[qid[q], fid[q[0]], q[1]] for q in queries])
    sample = [[r[0], "false", 0] for r in test_queries]
    answers = []
    for (p, b) in queries:
        t = cells[p][b]
        answers.append([qid[(p, b)], t, fid[p], b, test_regime[p], "yes" if test_regime[p] in HARD_REGIMES else "no",
                        "yes" if p.split(".")[0] in UNSEEN_CATEGORIES else "no",
                        dates[(b, t)] if t != "false" else "none"])
    answers.sort()

    # ---- write
    P, Q = os.path.join(args.out, "public"), os.path.join(args.out, "private")
    os.makedirs(P, exist_ok=True); os.makedirs(Q, exist_ok=True)

    def w(path, header, rows):
        with open(path, "w", newline="", encoding="utf-8") as f:
            wr = csv.writer(f); wr.writerow(header); wr.writerows(rows)
    w(os.path.join(P, "browsers.csv"), ["browser", "version", "release_date", "engine", "engine_version", "status", "upstream", "type"], browsers_rows)
    fh = ["feature_id", "parent_id", "category", "depth", "experimental", "standard_track", "deprecated"]
    w(os.path.join(P, "train_features.csv"), fh + ["regime"], train_features)
    w(os.path.join(P, "train_support.csv"), ["feature_id", "browser", "version_added"], train_support)
    w(os.path.join(P, "train_hidden.csv"), ["feature_id", "browser"], train_hidden_rows)
    w(os.path.join(P, "test_features.csv"), fh, test_features)
    w(os.path.join(P, "test_support.csv"), ["feature_id", "browser", "version_added"], test_support)
    w(os.path.join(P, "test_queries.csv"), ["id", "feature_id", "browser"], test_queries)
    w(os.path.join(P, "sample_submission.csv"), ["id", "prediction", "certain"], sample)
    w(os.path.join(Q, "answers.csv"), ["id", "target", "feature_id", "browser", "regime", "hard", "unseen_category", "target_date"], answers)
    w(os.path.join(Q, "feature_manifest.csv"), ["feature_id", "path", "split", "regime"],
      sorted([[fid[p], p, "train" if p in train_regime else "test", train_regime.get(p, test_regime.get(p, ""))] for p in paths]))
    from collections import Counter
    report = {
        "seed": args.seed, "bcd_version": meta.get("version"), "bcd_timestamp": meta.get("timestamp"),
        "n_features": len(paths), "n_train_features": len(train_paths), "n_test_features": len(test_paths),
        "n_train_cells": len(train_support), "n_test_visible_cells": len(test_support), "n_queries": len(queries),
        "regime_counts_test": dict(Counter(test_regime[p] for p in test_paths)),
        "regime_counts_train": dict(Counter(train_regime.values())),
        "query_regime_counts": dict(Counter(a[4] for a in answers)),
        "target_false_share": sum(1 for a in answers if a[1] == "false") / len(answers),
        "unseen_categories": sorted(UNSEEN_CATEGORIES), "n_test_l3_subtrees": len(test_l3),
        "browsers": BROWSERS, "n_release_rows": len(browsers_rows),
    }
    json.dump(report, open(os.path.join(Q, "prepare_report.json"), "w"), indent=2)
    verify(P, Q)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
