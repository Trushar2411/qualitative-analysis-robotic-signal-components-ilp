#!/usr/bin/env python3
"""Phase-aware PLA for Franka joint/finger positions and velocities.

Input: a labeled CSV or directory of labeled CSV files (time_seconds, phase,
       joint_1..7_position/velocity, finger_1..2_position/velocity).
Output per demo: nine combined position+velocity PLA CSVs; two all-signal
       position/velocity PLA CSVs; phase summaries and plots.
"""

from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PHASES = ("approach", "pick", "transport", "place", "retract")
SIGNALS = [f"joint_{i}" for i in range(1, 8)] + ["finger_1", "finger_2"]
TYPES = ("position", "velocity")
DEFAULT_THRESHOLDS = {"position": 0.005, "velocity": 0.010}
COLORS = {
    "ramp_up": "tab:green",
    "ramp_down": "tab:red",
    "constant": "tab:blue",
    "insufficient_data": "0.5",
}
PHASE_COLORS = {
    "approach": "#e9f3ff",
    "pick": "#fff1cf",
    "transport": "#e6f4e6",
    "place": "#f2e9ff",
    "retract": "#ffe9e9",
}


def label_for(change, threshold):
    return (
        "ramp_up"
        if change > threshold
        else "ramp_down" if change < -threshold else "constant"
    )


def phase_runs(phases):
    """Consecutive phase runs, not global grouping (prevents time discontinuities)."""
    start = 0
    for end in range(1, len(phases) + 1):
        if end == len(phases) or phases[end] != phases[start]:
            yield start, end, str(phases[start])
            start = end


def windows_within_phase(left, right, window, step):
    n = right - left
    if n < 2:
        yield left, right
    elif n < window:
        # Fit the entire short phase (2-4 samples) rather than crossing phases.
        yield left, right
    else:
        starts = list(range(left, right - window + 1, step))
        for start in starts:
            yield start, start + window
        # Retain short trailing remainder if >=2; avoid duplicate intervals.
        tail_start = starts[-1] + window
        if right - tail_start >= 2:
            yield tail_start, right


def fit_window(time, values, threshold):
    valid = np.isfinite(time) & np.isfinite(values)
    n = int(valid.sum())
    if n < 2:
        return {
            "label": "insufficient_data",
            "slope": np.nan,
            "change": np.nan,
            "intercept": np.nan,
            "start_value": np.nan,
            "end_value": np.nan,
            "mean_value": (
                float(np.nanmean(values)) if np.isfinite(values).any() else np.nan
            ),
            "valid_samples": n,
        }
    t = time[valid]
    y = values[valid]
    if np.unique(t).size < 2:
        return {
            "label": "insufficient_data",
            "slope": np.nan,
            "change": np.nan,
            "intercept": np.nan,
            "start_value": float(y[0]),
            "end_value": float(y[-1]),
            "mean_value": float(np.mean(y)),
            "valid_samples": n,
        }
    slope, intercept = np.polyfit(t - t[0], y, 1)
    intercept_global = float(intercept - slope * t[0])
    change = float(slope * (t[-1] - t[0]))
    return {
        "label": label_for(change, threshold),
        "slope": float(slope),
        "change": change,
        "intercept": intercept_global,
        "start_value": float(y[0]),
        "end_value": float(y[-1]),
        "mean_value": float(np.mean(y)),
        "valid_samples": n,
    }


def plot_kind(df, all_rows, kind, outpath):
    fig, axes = plt.subplots(
        9, 1, figsize=(15, 21), sharex=True, constrained_layout=True
    )
    time = df["time_seconds"].to_numpy(dtype=float)
    phase_seq = df["phase"].astype(str).str.lower().to_numpy()
    for idx, sig in enumerate(SIGNALS):
        ax = axes[idx]
        for left, right, phase in phase_runs(phase_seq):
            ax.axvspan(
                time[left],
                time[right - 1],
                color=PHASE_COLORS.get(phase, "#eeeeee"),
                alpha=0.55,
            )
        vals = df[f"{sig}_{kind}"].to_numpy(dtype=float)
        ax.plot(time, vals, color="0.65", lw=1.0, label="Raw")
        rows = all_rows[all_rows["signal"] == sig]
        for _, r in rows.iterrows():
            if not np.isfinite(r["slope"]):
                continue
            a, b = int(r["start_index"]), int(r["end_index"]) + 1
            xx = time[a:b]
            ax.plot(
                xx, r["slope"] * xx + r["intercept"], lw=2.0, color=COLORS[r["label"]]
            )
        ax.set_ylabel(sig.replace("joint_", "J").replace("finger_", "F"))
        ax.grid(alpha=0.2)
    axes[0].set_title(
        f'{df.attrs.get("demo_name", "Franka")} - {kind} PLA (green: up, red: down, blue: constant)'
    )
    axes[-1].set_xlabel("Elapsed time (seconds)")
    fig.savefig(outpath, dpi=145)
    plt.close(fig)


def process_file(path, output_root, window, step, thresholds, do_plots=True):
    df = pd.read_csv(path)
    required = ["time_seconds", "phase"] + [
        f"{sig}_{kind}" for sig in SIGNALS for kind in TYPES
    ]
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    for col in required:
        if col != "phase":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if len(df) == 0 or df["time_seconds"].isna().any() or df["phase"].isna().any():
        raise ValueError("Missing timestamps, phase labels, or empty CSV")
    df = df.sort_values("time_seconds", kind="stable").reset_index(drop=True)
    time = df["time_seconds"].to_numpy(dtype=float)
    if not np.all(np.isfinite(time)) or np.any(np.diff(time) <= 0):
        raise ValueError("time_seconds must be finite and strictly increasing")
    df["phase"] = df["phase"].astype(str).str.strip().str.lower()
    unknown = set(df["phase"]) - set(PHASES)
    if unknown:
        raise ValueError(f"Unrecognized phases: {sorted(unknown)}")
    out = output_root / path.stem
    (out / "per_joint").mkdir(parents=True, exist_ok=True)
    (out / "per_signal_type").mkdir(exist_ok=True)
    (out / "plots").mkdir(exist_ok=True)
    rows = []
    t = df["time_seconds"].to_numpy(dtype=float)
    for left, right, phase in phase_runs(df["phase"].to_numpy()):
        for lo, hi in windows_within_phase(left, right, window, step):
            base = {
                "demonstration": path.stem,
                "phase": phase,
                "start_index": lo,
                "end_index": hi - 1,
                "start_time_sec": float(t[lo]),
                "end_time_sec": float(t[hi - 1]),
                "duration_sec": float(t[hi - 1] - t[lo]),
                "samples": hi - lo,
            }
            for sig in SIGNALS:
                row = dict(base)
                row["signal"] = sig
                for kind in TYPES:
                    fit = fit_window(
                        t[lo:hi],
                        df[f"{sig}_{kind}"].to_numpy(dtype=float)[lo:hi],
                        thresholds[kind],
                    )
                    for key, value in fit.items():
                        row[f"{kind}_{key}"] = value
                rows.append(row)
    combined = pd.DataFrame(rows)
    combined.to_csv(out / "all_signals_combined_PLA.csv", index=False)
    for sig in SIGNALS:
        combined[combined["signal"] == sig].to_csv(
            out / "per_joint" / f"{sig}_PLA.csv", index=False
        )
    summaries = []
    for kind in TYPES:
        fields = [
            "demonstration",
            "phase",
            "signal",
            "start_index",
            "end_index",
            "start_time_sec",
            "end_time_sec",
            "duration_sec",
            "samples",
        ]
        extra = [
            f"{kind}_{key}"
            for key in (
                "label",
                "slope",
                "change",
                "intercept",
                "start_value",
                "end_value",
                "mean_value",
                "valid_samples",
            )
        ]
        simple = combined[fields + extra].copy()
        simple.columns = fields + [x.removeprefix(f"{kind}_") for x in extra]
        simple.to_csv(
            out / "per_signal_type" / f"pla_{kind}_all_joints.csv", index=False
        )
        for (phase, sig), sub in simple.groupby(["phase", "signal"], sort=False):
            counts = sub["label"].value_counts()
            valid = sub.loc[sub["label"] != "insufficient_data", "label"]
            summaries.append(
                {
                    "demonstration": path.stem,
                    "phase": phase,
                    "signal": sig,
                    "kind": kind,
                    "dominant_label": (
                        valid.mode().iloc[0] if not valid.empty else "insufficient_data"
                    ),
                    "ramp_up_windows": int(counts.get("ramp_up", 0)),
                    "ramp_down_windows": int(counts.get("ramp_down", 0)),
                    "constant_windows": int(counts.get("constant", 0)),
                    "insufficient_windows": int(counts.get("insufficient_data", 0)),
                    "total_windows": len(sub),
                }
            )
        if do_plots:
            df.attrs["demo_name"] = path.stem
            plot_kind(df, simple, kind, out / "plots" / f"{kind}_PLA.png")
    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(out / "phase_PLA_summary.csv", index=False)
    return combined, summary_df


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "input", type=Path, help="Labeled CSV or directory containing *_labeled.csv"
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs" / "PLA",
    )
    p.add_argument("--window", type=int, default=5)
    p.add_argument("--step", type=int, default=5)
    p.add_argument(
        "--position-threshold", type=float, default=DEFAULT_THRESHOLDS["position"]
    )
    p.add_argument(
        "--velocity-threshold", type=float, default=DEFAULT_THRESHOLDS["velocity"]
    )
    p.add_argument("--no-plots", action="store_true")
    args = p.parse_args()
    if (
        args.window < 2
        or args.step < 1
        or args.position_threshold < 0
        or args.velocity_threshold < 0
    ):
        p.error("window >=2, step >=1 and nonnegative thresholds required")
    paths = (
        sorted(args.input.glob("*_labeled.csv"))
        if args.input.is_dir()
        else [args.input]
    )
    if not paths:
        p.error("No *_labeled.csv files found")
    args.output.mkdir(parents=True, exist_ok=True)
    summaries = []
    failures = []
    for path in paths:
        try:
            combined, summary = process_file(
                path,
                args.output,
                args.window,
                args.step,
                {
                    "position": args.position_threshold,
                    "velocity": args.velocity_threshold,
                },
                not args.no_plots,
            )
            summaries.append(summary)
            print(
                f"OK {path.name}: {len(combined)//9} windows per signal; 9 joint CSVs + 2 aggregate CSVs"
            )
        except (ValueError, OSError, KeyError) as exc:
            failures.append({"file": path.name, "reason": str(exc)})
            print(f"SKIPPED {path.name}: {exc}")
    if summaries:
        pd.concat(summaries, ignore_index=True).to_csv(
            args.output / "all_demos_phase_PLA_summary.csv", index=False
        )
    if failures:
        pd.DataFrame(failures).to_csv(args.output / "failed_files.csv", index=False)
    print(f"Done: {len(summaries)}/{len(paths)} demos processed. Output: {args.output}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
