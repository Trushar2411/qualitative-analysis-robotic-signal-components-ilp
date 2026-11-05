#!/usr/bin/env python3
"""Check unlabelled xArm6 position CSVs against the supplied Popper hypotheses.

Install: python3 -m pip install numpy pandas
Run:     python3 check_pick_place.py /path/to/new_recording.csv
         python3 check_pick_place.py  # prompts for a CSV path

No Popper, Prolog, ROS, phase column, velocity or effort is required.
Outputs: windows.csv, events.csv and report.json beside the input, in a new
<stem>_pick_place_check directory (override with --output-dir).

The position encoding matches prepare_popper.py: least-squares line per
20-sample window, fitted end-to-end change; arm threshold 0.004 rad and
finger threshold 0.001 rad. Unlike training, window boundaries never use
phase labels. Thus predictions need not reproduce the training counts.

Each rule is applied independently, so a window may match several actions.
Two consecutive matching windows make an event by default. Detection requires
non-overlapping events ordered as pick -> gripper_closing -> lift -> place ->
gripper_opening. This ordering and persistence filter are added heuristics,
not rules learned by Popper. Home and return_home are reported but optional.
No retract rule exists in the supplied successful hypotheses.

PATTERN_DETECTED means evidence of the learned motion pattern, not verified
object pickup, task success, or a calibrated classifier probability.
INSUFFICIENT_EVIDENCE does not prove the recording lacks pick and place.
Use recordings with the same robot, joint convention, units and comparable
sampling rate. These hypotheses have not been validated on unseen recordings.

Examples:
  python3 check_pick_place.py new.csv --min-consecutive 1
  python3 check_pick_place.py new.csv --time-column time_seconds
  python3 check_pick_place.py new.csv --time-column timestamp --time-unit ns
  python3 check_pick_place.py new.csv --column-map '{"joint1_position":"j1"}'

Without a known timestamp column, the fit uses sample index and outputs row
ranges; no timestamps are invented. For irregular sampling, supply real times.
CSV rows in reports are zero-based data rows, excluding the header.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
except ImportError:
    raise SystemExit("Install dependencies: python3 -m pip install numpy pandas")


# An outer tuple is OR; predicates inside a clause are AND.
RULES = {
    "gripper_closing": (("right_finger_joint_position_increases",),),
    "gripper_opening": (("right_finger_joint_position_decreases",),),
    "home": (("joint2_position_decreases", "joint5_position_constant"),),
    "lift": (("joint1_position_decreases", "joint3_position_decreases"),),
    "pick": (("joint3_position_decreases", "joint2_position_increases"),),
    "place": (
        ("joint5_position_decreases", "joint3_position_constant"),
        ("joint5_position_decreases", "joint1_position_increases"),
    ),
    "return_home": (("joint5_position_increases", "joint1_position_increases"),),
}
SEQUENCE = ("pick", "gripper_closing", "lift", "place", "gripper_opening")
SIGNALS = ("joint1_position", "joint2_position", "joint3_position",
           "joint5_position", "right_finger_joint_position")
TIME_COLUMNS = ("header_stamp_sec", "time_seconds", "time_sec", "timestamp_sec",
                "bag_time_sec", "header_stamp_ns", "bag_time_ns", "timestamp_ns")
EVENT_COLUMNS = ["event_id", "action", "start_window", "end_window", "windows",
                 "start_row", "end_row", "start_time_sec", "end_time_sec"]


def parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv", nargs="?", help="CSV to check; prompts if omitted")
    p.add_argument("--output-dir", type=Path)
    p.add_argument("--window", type=int, default=20, help="Samples per window (default: 20)")
    p.add_argument("--step", type=int, default=20, help="Window stride (default: 20)")
    p.add_argument("--min-samples", type=int, default=8)
    p.add_argument("--threshold", type=float, default=0.004,
                   help="Arm fitted-change threshold in radians")
    p.add_argument("--finger-threshold", type=float, default=0.001)
    p.add_argument("--min-consecutive", type=int, default=2,
                   help="Consecutive rule matches per event (default: 2)")
    p.add_argument("--max-gap-windows", type=int, default=50,
                   help="Maximum unmatched windows between sequence stages (default: 50)")
    p.add_argument("--max-cycle-windows", type=int, default=250,
                   help="Maximum windows spanning a candidate cycle (default: 250)")
    p.add_argument("--max-time-gap", type=float, default=1.0,
                   help="Split recording at time gaps above this many seconds; 0 disables")
    p.add_argument("--time-column", help="Optional real numeric timestamp column")
    p.add_argument("--time-unit", choices=("auto", "s", "ms", "us", "ns"), default="auto")
    p.add_argument("--column-map", default="{}",
                   help='JSON mapping canonical names to CSV names, e.g. '
                        '\'{"joint1_position":"j1_pos"}\'')
    return p


def resolve_columns(df, mapping):
    """Accept spelling variants, but never silently substitute another finger."""
    found = {}
    for signal in SIGNALS:
        candidates = [signal]
        m = re.fullmatch(r"joint([1-6])_position", signal)
        if m:
            candidates.append(f"joint_{m.group(1)}_position")
        if signal == "right_finger_joint_position":
            candidates.append("right_finger_position")
        if signal in mapping:
            candidates = [mapping[signal]]
        matches = [c for c in candidates if c in df.columns]
        if not matches:
            raise ValueError(f"Missing {signal}. Supply this column or --column-map. "
                             "Do not map an unrelated robot joint to this signal.")
        found[signal] = matches[0]
    if len(set(found.values())) != len(found):
        raise ValueError("Each required signal must map to a different CSV column.")
    return found


def read_times(df, args, warnings):
    col = args.time_column or next((c for c in TIME_COLUMNS if c in df), None)
    if col is None:
        if args.time_unit != "auto":
            raise ValueError("--time-unit requires a real time column.")
        warnings.append("No known timestamp column: fitting against sample index. "
                        "Row order is assumed chronological; sampling irregularity is unknown.")
        return np.arange(len(df), dtype=float), None, None
    if col not in df:
        raise ValueError(f"Time column not found: {col}")
    values = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(f"Time column {col} contains missing or non-numeric values.")
    unit = args.time_unit
    if unit == "auto":
        unit = next((u for u in ("ns", "us", "ms") if col.endswith("_" + u)), "s")
        if col not in TIME_COLUMNS and not col.endswith(("_s", "_sec", "_seconds", "_ns", "_us", "_ms")):
            warnings.append(f"Assuming {col} is in seconds; use --time-unit if needed.")
    seconds = values * {"s": 1.0, "ms": 1e-3, "us": 1e-6, "ns": 1e-9}[unit]
    if not np.isfinite(seconds).all():
        raise ValueError("Converted times are not finite.")
    return seconds, col, unit


def split_blocks(times, has_time, max_gap):
    """Never build windows or sequences across clock resets or recording gaps."""
    if not has_time:
        return [(0, len(times))]
    dt = np.diff(times)
    split = dt <= 0
    if max_gap > 0:
        split |= dt > max_gap
    bounds = [0, *(np.flatnonzero(split) + 1).tolist(), len(times)]
    return list(zip(bounds[:-1], bounds[1:]))


def make_windows(df, times, columns, args, has_time):
    values = {s: pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float)
              for s, c in columns.items()}
    blocks = split_blocks(times, has_time, args.max_time_gap)
    records = []
    for block_id, (lo, hi) in enumerate(blocks):
        for start in range(lo, hi, args.step):
            end = min(start + args.window, hi)
            if end - start < args.min_samples:
                continue
            row = {"window_id": len(records), "block_id": block_id,
                   "start_row": start, "end_row": end - 1, "samples": end - start,
                   "start_time_sec": float(times[start]) if has_time else None,
                   "end_time_sec": float(times[end - 1]) if has_time else None}
            predicates = set()
            for signal, array in values.items():
                y = array[start:end]
                t = times[start:end]
                good = np.isfinite(y) & np.isfinite(t)
                change = None
                label = "unknown"
                if good.sum() >= args.min_samples:
                    tg, yg = t[good], y[good]
                    dt = tg[-1] - tg[0]
                    if dt > 0:
                        change = float(np.polyfit(tg - tg[0], yg, 1)[0] * dt)
                        threshold = (args.finger_threshold if signal.startswith("right_finger")
                                     else args.threshold)
                        label = ("increases" if change > threshold else
                                 "decreases" if change < -threshold else "constant")
                        predicates.add(f"{signal}_{label}")
                row[f"{signal}_fitted_change"] = change
                row[f"{signal}_trend"] = label
            matches = []
            for action, clauses in RULES.items():
                fired = [str(i + 1) for i, clause in enumerate(clauses)
                         if all(pred in predicates for pred in clause)]
                row[f"match_{action}"] = bool(fired)
                row[f"clauses_{action}"] = ";".join(fired)
                if fired:
                    matches.append(action)
            row["matching_actions"] = ";".join(matches)
            records.append(row)
    if not records:
        raise ValueError("No usable windows. Check row count, timestamps or --min-samples.")
    return pd.DataFrame(records), len(blocks), values


def make_events(windows, minimum):
    events = []
    for action in RULES:
        active = windows[f"match_{action}"].to_numpy(dtype=bool)
        blocks = windows["block_id"].to_numpy()
        i = 0
        while i < len(windows):
            if not active[i]:
                i += 1
                continue
            j = i + 1
            while j < len(windows) and active[j] and blocks[j] == blocks[i]:
                j += 1
            if j - i >= minimum:
                first, last = windows.iloc[i], windows.iloc[j - 1]
                events.append({"action": action, "block_id": int(blocks[i]),
                               "start_window": i, "end_window": j - 1, "windows": j - i,
                               "start_row": int(first["start_row"]),
                               "end_row": int(last["end_row"]),
                               "start_time_sec": first["start_time_sec"],
                               "end_time_sec": last["end_time_sec"]})
            i = j
    events.sort(key=lambda e: (e["start_window"], e["end_window"], e["action"]))
    for i, event in enumerate(events):
        event["event_id"] = i
    return events


def find_cycles(events, args):
    """Ordered event matching; keep all rule labels, never use phase/cycle labels."""
    cycles = []
    consumed_row = -1
    for seed in (e for e in events if e["action"] == SEQUENCE[0]):
        if seed["start_row"] <= consumed_row:
            continue
        paths = [[seed]]
        for stage in SEQUENCE[1:]:
            candidates = []
            for event in events:
                if event["action"] != stage or event["block_id"] != seed["block_id"]:
                    continue
                if event["end_window"] - seed["start_window"] + 1 > args.max_cycle_windows:
                    continue
                for path in paths:
                    previous = path[-1]
                    gap = event["start_window"] - previous["end_window"] - 1
                    # Row check also excludes overlap when --step < --window.
                    if (0 <= gap <= args.max_gap_windows and
                            event["start_row"] > previous["end_row"]):
                        candidates.append(path + [event])
                        break  # One valid prefix per event suffices for this seed.
            paths = candidates
            if not paths:
                break
        if paths:
            best = min(paths, key=lambda path: path[-1]["end_row"])
            cycles.append({"cycle_id": len(cycles) + 1,
                           "start_row": seed["start_row"],
                           "end_row": best[-1]["end_row"],
                           "start_time_sec": seed["start_time_sec"],
                           "end_time_sec": best[-1]["end_time_sec"],
                           "events": best})
            consumed_row = best[-1]["end_row"]
    return cycles


def run(args):
    src = Path(args.csv).expanduser().resolve()
    if not src.is_file():
        raise ValueError(f"CSV not found: {src}")
    df = pd.read_csv(src)
    if df.empty:
        raise ValueError("CSV contains no data rows.")
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]
    if len(set(df.columns)) != len(df.columns):
        raise ValueError("CSV has duplicate column names after whitespace removal.")
    try:
        mapping = json.loads(args.column_map)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--column-map must be valid JSON: {exc}") from exc
    if not isinstance(mapping, dict) or any(not isinstance(v, str) for v in mapping.values()):
        raise ValueError("--column-map must be a JSON object with string values.")
    if set(mapping) - set(SIGNALS):
        raise ValueError(f"Unknown canonical column names: {sorted(set(mapping) - set(SIGNALS))}")
    columns = resolve_columns(df, mapping)
    warnings = [
        "Hypotheses were learned on one recording; unseen-data performance is unvalidated.",
        "Phase, phase_id, cycle and other label columns are ignored.",
        "Global windows can cross action transitions; training used phase-bounded windows.",
        "Window sizes and thresholds depend on sampling rate, units and joint convention.",
        "No learned retract rule: the supplied retract/1 task failed.",
        "Motion-pattern detection cannot verify object contact, grasp or placement success.",
    ]
    times, time_col, time_unit = read_times(df, args, warnings)
    windows, block_count, values = make_windows(df, times, columns, args, time_col is not None)
    invalid = {s: int((~np.isfinite(v)).sum()) for s, v in values.items()
               if not np.isfinite(v).all()}
    if invalid:
        warnings.append(f"Non-numeric/missing position samples: {invalid}. "
                        "Each fit needs --min-samples finite observations; otherwise trend is unknown.")
    if block_count > 1:
        warnings.append(f"Split into {block_count} blocks at non-increasing times or long gaps. "
                        "Sequences never cross these boundaries.")
    events = make_events(windows, args.min_consecutive)
    cycles = find_cycles(events, args)
    event_counts = {a: sum(e["action"] == a for e in events) for a in RULES}
    report = {
        "input_csv": str(src), "status": "PATTERN_DETECTED" if cycles else "INSUFFICIENT_EVIDENCE",
        "interpretation": ("Ordered pick-and-place motion pattern detected." if cycles else
                           "No complete ordered pattern under the current rules and settings; "
                           "this is not proof that pick and place did not occur."),
        "rows": len(df), "windows": len(windows), "blocks": block_count,
        "time_column": time_col, "time_unit": time_unit, "column_mapping": columns,
        "settings": {k: getattr(args, k) for k in ("window", "step", "min_samples", "threshold",
                     "finger_threshold", "min_consecutive", "max_gap_windows",
                     "max_cycle_windows", "max_time_gap")},
        "sequence_required": list(SEQUENCE), "sequence_source": "manually specified heuristic",
        "rules": RULES,
        "window_matches": {a: int(windows[f"match_{a}"].sum()) for a in RULES},
        "event_counts": event_counts,
        "stages_without_events": [s for s in SEQUENCE if not event_counts[s]],
        "detected_cycles": len(cycles), "cycles": cycles, "warnings": warnings,
        "precision": None, "recall": None,
        "metrics_note": "No ground-truth labels used. Precision and recall cannot be computed.",
    }
    out = (args.output_dir or src.parent / (src.stem + "_pick_place_check")).expanduser().resolve()
    # Do not permit an output filename to replace the input accidentally.
    if src in [out / n for n in ("windows.csv", "events.csv", "report.json")]:
        raise ValueError("Output location would overwrite the input CSV.")
    out.mkdir(parents=True, exist_ok=True)
    windows.to_csv(out / "windows.csv", index=False)
    pd.DataFrame(events, columns=EVENT_COLUMNS + ["block_id"]).to_csv(out / "events.csv", index=False)
    (out / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"\nResult: {report['status']}")
    print(report["interpretation"])
    print(f"Rows: {len(df)} | windows: {len(windows)} | detected cycles: {len(cycles)}")
    print("\nAction                 Matching windows   Sustained events")
    for action in RULES:
        print(f"{action:<23}{report['window_matches'][action]:>10}{event_counts[action]:>19}")
    if report["stages_without_events"]:
        print("\nStages without sustained evidence: " + ", ".join(report["stages_without_events"]))
    elif not cycles:
        print("\nAction evidence exists, but order, overlap, gap or cycle-length checks failed.")
    for cycle in cycles:
        print(f"\nCycle {cycle['cycle_id']}: data rows {cycle['start_row']}–{cycle['end_row']}")
        print(" -> ".join(e["action"] for e in cycle["events"]))
        if time_col:
            print(f"Time: {cycle['start_time_sec']:.6f}–{cycle['end_time_sec']:.6f} seconds")
    print("\nLimits: one-recording hypotheses; motion evidence only. "
          "No precision/recall without ground truth.")
    for warning in warnings[6:]:
        print("Warning: " + warning)
    print(f"\nSaved: {out / 'windows.csv'}\nSaved: {out / 'events.csv'}\nSaved: {out / 'report.json'}")
    return report


def main():
    p = parser()
    a = p.parse_args()
    if not a.csv:
        if not sys.stdin.isatty():
            p.error('Provide a CSV path: python3 check_pick_place.py "/path/to/new.csv"')
        a.csv = input("CSV path to check: ").strip().strip('"').strip("'")
    if not a.csv:
        p.error("CSV path is empty.")
    if not (2 <= a.min_samples <= a.window and 1 <= a.step <= a.window):
        p.error("Require 2 <= min-samples <= window and 1 <= step <= window.")
    if a.min_consecutive < 1 or a.max_gap_windows < 0 or a.max_cycle_windows < 1:
        p.error("Require min-consecutive >= 1, max-gap-windows >= 0, max-cycle-windows >= 1.")
    for name in ("threshold", "finger_threshold", "max_time_gap"):
        if not math.isfinite(getattr(a, name)) or getattr(a, name) < 0:
            p.error(f"{name.replace('_', '-')} must be finite and non-negative.")
    try:
        run(a)
    except (ValueError, OSError, pd.errors.ParserError) as exc:
        p.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
