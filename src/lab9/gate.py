"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def _is_bad_number(val: Any) -> bool:
    if isinstance(val, bool):
        return False
    if isinstance(val, (int, float)):
        return math.isnan(val) or math.isinf(val)
    return True


def _check_ratchet(spec: dict, base_spec: dict) -> list[str]:
    problems: list[str] = []
    if spec.get("eval_set_version") != base_spec.get("eval_set_version"):
        return problems

    base_metrics = {m["id"]: m for m in (base_spec.get("metrics") or [])}
    curr_metrics = {m["id"]: m for m in (spec.get("metrics") or [])}
    for mid, bm in base_metrics.items():
        if mid not in curr_metrics:
            problems.append(f"ratchet: metric {mid!r} was removed from spec")
            continue
        cm = curr_metrics[mid]
        if bm.get("blocking") and not cm.get("blocking"):
            problems.append(f"ratchet: blocking metric {mid!r} became non-blocking")
        bth = bm.get("threshold") or {}
        cth = cm.get("threshold") or {}
        if "min" in bth:
            if "min" not in cth or cth["min"] < bth["min"] - 1e-12:
                problems.append(f"ratchet: metric {mid!r} min threshold lowered from {bth['min']} to {cth.get('min')}")
        if "max" in bth:
            if "max" not in cth or cth["max"] > bth["max"] + 1e-12:
                problems.append(f"ratchet: metric {mid!r} max threshold raised from {bth['max']} to {cth.get('max')}")
        if "max_increase" in bth:
            if "max_increase" not in cth or cth["max_increase"] > bth["max_increase"] + 1e-12:
                problems.append(
                    f"ratchet: metric {mid!r} max_increase raised from {bth['max_increase']} to {cth.get('max_increase')}"
                )
        if bth.get("no_significant_drop") and not cth.get("no_significant_drop"):
            problems.append(f"ratchet: metric {mid!r} dropped no_significant_drop")

    base_slices = {(s["name"], s["metric"]): s for s in (base_spec.get("slices") or [])}
    curr_slices = {(s["name"], s["metric"]): s for s in (spec.get("slices") or [])}
    for key, bs in base_slices.items():
        sname, smetric = key
        if key not in curr_slices:
            problems.append(f"ratchet: slice {sname}/{smetric} was removed from spec")
            continue
        cs = curr_slices[key]
        if bs.get("blocking") and not cs.get("blocking"):
            problems.append(f"ratchet: blocking slice {sname}/{smetric} became non-blocking")
        if "min" in bs:
            if "min" not in cs or cs["min"] < bs["min"] - 1e-12:
                problems.append(
                    f"ratchet: slice {sname}/{smetric} min threshold lowered from {bs['min']} to {cs.get('min')}"
                )
        if bs.get("no_significant_drop") and not cs.get("no_significant_drop"):
            problems.append(f"ratchet: slice {sname}/{smetric} dropped no_significant_drop")

    return problems


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate."""
    problems: list[str] = []

    if base_spec is not None:
        problems.extend(_check_ratchet(spec, base_spec))

    if pr.get("evaluator_failures"):
        problems.append(f"evaluator_failures non-empty ({len(pr['evaluator_failures'])})")
    if base.get("evaluator_failures"):
        problems.append(f"baseline evaluator_failures non-empty ({len(base['evaluator_failures'])})")

    pr_metrics = pr.get("metrics") or {}
    passes = sum(bool(r.get("pass_rate")) for r in (pr.get("rows") or []))
    for k, v in pr_metrics.items():
        if v is None:
            if k == "cost_per_success" and passes == 0:
                continue
            problems.append(f"metric {k!r} has invalid value {v!r}")
        elif _is_bad_number(v):
            problems.append(f"metric {k!r} has invalid value {v!r}")
    for m in spec.get("metrics") or []:
        mid = m["id"]
        if mid not in pr_metrics:
            problems.append(f"spec metric {mid!r} missing in pr['metrics']")
        elif pr_metrics.get(mid) is None:
            if mid == "cost_per_success" and passes == 0:
                continue
            problems.append(f"spec metric {mid!r} is None in pr['metrics']")
        elif _is_bad_number(pr_metrics.get(mid)):
            problems.append(f"spec metric {mid!r} is NaN/inf in pr['metrics']")

    pr_manifest = pr.get("manifest") or {}
    base_manifest = base.get("manifest") or {}
    pr_rows = pr.get("rows") or []
    base_rows = base.get("rows") or []

    expected_pr_len = int(pr_manifest.get("items") or 0) * len(pr_manifest.get("seeds") or [])
    if len(pr_rows) != expected_pr_len:
        problems.append(f"row count {len(pr_rows)} != manifest items*seeds ({expected_pr_len})")
    if len(pr_rows) != len(base_rows):
        problems.append(f"PR row count {len(pr_rows)} != baseline row count {len(base_rows)}")

    if pr_manifest.get("items") != base_manifest.get("items") or list(pr_manifest.get("seeds") or []) != list(
        base_manifest.get("seeds") or []
    ):
        problems.append("manifest items or seeds differ from baseline")

    pr_pairs = [(r.get("item_id"), r.get("seed")) for r in pr_rows]
    base_pairs = [(r.get("item_id"), r.get("seed")) for r in base_rows]
    if len(set(pr_pairs)) != len(pr_pairs):
        problems.append("duplicate (item_id, seed) rows in PR report")
    if set(pr_pairs) != set(base_pairs):
        problems.append("(item_id, seed) set of PR differs from baseline")

    # Verify graded metrics in rows are present, boolean/valid, not None/NaN
    row_metric_ids = [
        m["id"]
        for m in (spec.get("metrics") or [])
        if m["id"] in GRADERS or any(m["id"] in r for r in pr_rows + base_rows)
    ]
    for r in pr_rows:
        for mid in row_metric_ids:
            val = r.get(mid)
            if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
                problems.append(f"row {r.get('item_id')}@{r.get('seed')} has missing/NaN value for {mid!r}")
                break

    # Check item slice tags match baseline
    base_slices_by_item: dict[Any, list[str]] = {}
    for r in base_rows:
        base_slices_by_item.setdefault(r.get("item_id"), sorted(r.get("slices") or []))
    for r in pr_rows:
        iid = r.get("item_id")
        row_slices = sorted(r.get("slices") or [])
        if iid in base_slices_by_item and row_slices != base_slices_by_item[iid]:
            problems.append(f"slice tags for item {iid!r} differ from baseline ({row_slices} vs {base_slices_by_item[iid]})")
            break

    # Check reported metrics match recomputed aggregate from rows when rows contain the graded metrics
    if not problems and pr_rows and row_metric_ids:
        safe_rows = [{"cost": 0.0, **r} for r in pr_rows]
        recomputed = aggregate(safe_rows, row_metric_ids, k_values=spec.get("pass_k", []))
        for k, calc_val in recomputed.items():
            if k == "cost_per_success" and not all("cost" in r for r in pr_rows):
                continue
            if k in pr_metrics and calc_val is not None and isinstance(pr_metrics[k], (int, float)):
                if not _is_bad_number(pr_metrics[k]) and abs(float(pr_metrics[k]) - float(calc_val)) > 1e-3:
                    problems.append(
                        f"metric {k!r} in report ({pr_metrics[k]}) disagrees with rows aggregate ({calc_val})"
                    )

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        sname = s["name"]
        mid = s["metric"]
        sid = f"slice:{sname}/{mid}"
        a = per_item(pr, mid, slice_name=sname)
        b = per_item(base, mid, slice_name=sname)
        val = round(sum(a.values()) / len(a), 4) if a else None
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "min" in s and val < s["min"]:
            verdict = "fail"
        elif "max" in s and val > s["max"]:
            verdict = "fail"
        if s.get("no_significant_drop") and val is not None and a and b:
            keys = sorted(set(a) & set(b))
            if keys:
                d, lo, hi = stats.paired_bootstrap(
                    [a[k] for k in keys],
                    [b[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000),
                    rng=bs.get("rng", 2027),
                )
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(sid)
        th = {k: s[k] for k in ("min", "max", "no_significant_drop") if k in s}
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if s.get("blocking") else "warn")
        lines.append(f"  {sid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
