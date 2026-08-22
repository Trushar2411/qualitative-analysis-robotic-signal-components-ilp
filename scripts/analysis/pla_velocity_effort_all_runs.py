from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DATA_DIR = REPO_ROOT / "Processed data"
OUTPUT_ROOT = REPO_ROOT / "outputs" / "PLA_velocity_effort"

WINDOW_SIZE = 20
STEP = 20
PLA_SEGMENTS = 4

# Slope thresholds are expressed in signal-units/second. Adjust these values
# after checking the scale and noise level of the recorded robot signals.
DIRECTION_THRESHOLDS = {
    "velocity": 0.02,
    "effort": 0.02,
}

SIGNAL_LABELS = {
    "velocity": "Joint velocity [rad/s]",
    "effort": "Joint effort",
}

PHASE_COLORS = {
    "home": "#d9eaf7",
    "pick": "#fce8b2",
    "lift": "#d9ead3",
    "place": "#eadcf8",
    "retract": "#f4cccc",
    "unknown": "#eeeeee",
}

PLA_COLORS = {
    "ramp_up": "tab:green",
    "ramp_down": "tab:red",
    "constant": "tab:blue",
}


def natural_sort_key(path: Path) -> tuple[object, ...]:
    """Sort run_2 before run_10 without requiring a naming convention."""
    import re

    return tuple(
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    )


def find_processed_runs(processed_data_dir: Path) -> list[Path]:
    if not processed_data_dir.exists():
        raise FileNotFoundError(
            f"Processed data folder not found: {processed_data_dir}"
        )

    runs = sorted(
        (
            path
            for path in processed_data_dir.iterdir()
            if path.is_dir() and any(path.glob("joint_*.csv"))
        ),
        key=natural_sort_key,
    )
    if not runs:
        raise FileNotFoundError(
            f"No run folders containing joint_*.csv found in {processed_data_dir}"
        )
    return runs


def load_joint_signal(joint_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(joint_csv)
    required = ["joint", "bag_time_sec", "velocity", "effort", "phase"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"{joint_csv.name} is missing: {', '.join(missing)}")

    signal = df[required].copy()
    for column in ("bag_time_sec", "velocity", "effort"):
        signal[column] = pd.to_numeric(signal[column], errors="coerce")

    signal = signal.dropna(subset=["bag_time_sec", "velocity", "effort"])
    signal = signal.rename(columns={"bag_time_sec": "time_sec"})
    signal = signal[
        np.isfinite(signal["time_sec"])
        & np.isfinite(signal["velocity"])
        & np.isfinite(signal["effort"])
    ]
    signal["phase"] = signal["phase"].fillna("unknown").astype(str)
    signal = signal.sort_values("time_sec").reset_index(drop=True)

    if len(signal) < WINDOW_SIZE:
        raise ValueError(f"needs at least {WINDOW_SIZE} valid samples")
    return signal


def direction_label(slope: float, signal_name: str) -> str:
    threshold = DIRECTION_THRESHOLDS[signal_name]
    if slope > threshold:
        return "ramp_up"
    if slope < -threshold:
        return "ramp_down"
    return "constant"


def dominant_phase(phases: pd.Series) -> str:
    valid = phases.dropna()
    return "unknown" if valid.empty else str(valid.value_counts().idxmax())


def build_pla_segments(signal: pd.DataFrame, signal_name: str) -> pd.DataFrame:
    times = signal["time_sec"].to_numpy(dtype=float)
    values = signal[signal_name].to_numpy(dtype=float)
    joint_name = str(signal["joint"].iloc[0])
    rows: list[dict[str, object]] = []

    for start in range(0, len(values) - WINDOW_SIZE + 1, STEP):
        indices_in_window = np.arange(start, start + WINDOW_SIZE)
        for indices in np.array_split(indices_in_window, PLA_SEGMENTS):
            if len(indices) < 2:
                continue
            segment_time = times[indices]
            segment_values = values[indices]
            slope, intercept = np.polyfit(segment_time, segment_values, 1)
            rows.append(
                {
                    "segment_id": len(rows),
                    "joint": joint_name,
                    "signal": signal_name,
                    "start_time_sec": float(segment_time[0]),
                    "end_time_sec": float(segment_time[-1]),
                    "duration_sec": float(segment_time[-1] - segment_time[0]),
                    "phase": dominant_phase(signal.iloc[indices]["phase"]),
                    "label": direction_label(float(slope), signal_name),
                    "slope": float(slope),
                    "intercept": float(intercept),
                    "start_value": float(segment_values[0]),
                    "end_value": float(segment_values[-1]),
                    "mean_value": float(np.mean(segment_values)),
                }
            )
    return pd.DataFrame(rows)


def merge_same_labels(pla: pd.DataFrame) -> pd.DataFrame:
    if pla.empty:
        return pla

    merged: list[dict[str, object]] = []
    current = pla.iloc[0].to_dict()
    for _, next_row in pla.iloc[1:].iterrows():
        row = next_row.to_dict()
        if row["label"] == current["label"] and row["phase"] == current["phase"]:
            current["end_time_sec"] = row["end_time_sec"]
            current["duration_sec"] = (
                current["end_time_sec"] - current["start_time_sec"]
            )
            current["end_value"] = row["end_value"]
            current["mean_value"] = (
                current["start_value"] + current["end_value"]
            ) / 2.0
            current["slope"] = (
                current["end_value"] - current["start_value"]
            ) / max(current["duration_sec"], 1e-9)
            current["intercept"] = (
                current["start_value"]
                - current["slope"] * current["start_time_sec"]
            )
        else:
            merged.append(current)
            current = row
    merged.append(current)
    result = pd.DataFrame(merged)
    result["segment_id"] = range(len(result))
    return result


def phase_intervals(signal: pd.DataFrame) -> list[tuple[float, float, str]]:
    phases = signal["phase"].to_numpy(dtype=str)
    times = signal["time_sec"].to_numpy(dtype=float)
    changes = np.flatnonzero(phases[1:] != phases[:-1]) + 1
    bounds = np.concatenate(([0], changes, [len(signal)]))
    return [
        (float(times[left]), float(times[right - 1]), str(phases[left]))
        for left, right in zip(bounds[:-1], bounds[1:])
    ]


def add_phase_background(axis: plt.Axes, signal: pd.DataFrame, labels: bool) -> None:
    for start, end, phase in phase_intervals(signal):
        axis.axvspan(
            start,
            end,
            color=PHASE_COLORS.get(phase.lower(), PHASE_COLORS["unknown"]),
            alpha=0.28,
            linewidth=0,
            zorder=0,
        )
        if labels and end > start:
            axis.text(
                (start + end) / 2,
                0.98,
                phase.replace("_", " ").title(),
                transform=axis.get_xaxis_transform(),
                ha="center",
                va="top",
                fontsize=8,
                color="0.25",
            )


def style_axis(axis: plt.Axes, ylabel: str) -> None:
    axis.set_ylabel(ylabel)
    axis.grid(True, linestyle="--", alpha=0.35)
    axis.axhline(0, color="black", linewidth=0.8, alpha=0.55)


def plot_raw_and_pla(
    axis: plt.Axes,
    signal: pd.DataFrame,
    pla: pd.DataFrame,
    signal_name: str,
    show_legend: bool = True,
) -> None:
    """Draw the raw trace and the actual best-fit line for every PLA segment."""
    times = signal["time_sec"].to_numpy(dtype=float)
    values = signal[signal_name].to_numpy(dtype=float)
    axis.plot(
        times,
        values,
        color="0.72",
        linewidth=1.1,
        label=f"Raw {signal_name}",
        zorder=1,
    )

    labels_added: set[str] = set()
    for _, row in pla.iterrows():
        start_time = float(row["start_time_sec"])
        end_time = float(row["end_time_sec"])
        mask = (times >= start_time) & (times <= end_time)
        segment_time = times[mask]
        segment_values = values[mask]
        if len(segment_time) < 2:
            continue

        # Refit the complete merged interval. The colored line is therefore
        # the piecewise linear approximation, not a connection between raw
        # endpoints.
        slope, intercept = np.polyfit(segment_time, segment_values, 1)
        label = str(row["label"])
        axis.plot(
            segment_time,
            slope * segment_time + intercept,
            color=PLA_COLORS[label],
            linewidth=2.5,
            label=(
                label.replace("_", " ").title()
                if label not in labels_added
                else None
            ),
            zorder=3,
        )
        labels_added.add(label)

    if show_legend:
        axis.legend(loc="best", ncol=2)


def save_joint_pla_plot(
    signal: pd.DataFrame,
    pla: pd.DataFrame,
    signal_name: str,
    output: Path,
) -> None:
    times = signal["time_sec"].to_numpy(dtype=float)
    values = signal[signal_name].to_numpy(dtype=float)
    joint_name = str(signal["joint"].iloc[0])
    fig, axis = plt.subplots(figsize=(14, 7), constrained_layout=True)
    add_phase_background(axis, signal, labels=True)
    plot_raw_and_pla(axis, signal, pla, signal_name)

    axis.set_title(f"{joint_name} {signal_name.title()}: Raw Data and PLA")
    axis.set_xlabel("Time since run start [s]")
    style_axis(axis, SIGNAL_LABELS[signal_name])
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)


def save_all_joints_plot(
    signals: dict[str, pd.DataFrame],
    pla_results: dict[tuple[str, str], pd.DataFrame],
    signal_name: str,
    output: Path,
) -> None:
    ordered = sorted(signals.items())
    fig, axes = plt.subplots(
        len(ordered),
        1,
        figsize=(16, max(4 * len(ordered), 8)),
        sharex=True,
        squeeze=False,
        constrained_layout=True,
    )
    reference = max(signals.values(), key=len)
    for index, (joint_name, signal) in enumerate(ordered):
        axis = axes[index, 0]
        add_phase_background(axis, reference, labels=index == 0)
        plot_raw_and_pla(
            axis,
            signal,
            pla_results[(joint_name, signal_name)],
            signal_name,
            show_legend=index == 0,
        )
        style_axis(axis, SIGNAL_LABELS[signal_name])
        axis.set_title(f"{joint_name} {signal_name.title()} PLA")
    axes[-1, 0].set_xlabel("Time since run start [s]")
    fig.suptitle(
        f"All Joint {signal_name.title()} Piecewise Linear Approximations",
        fontsize=16,
    )
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)


def save_velocity_effort_plot(
    signals: dict[str, pd.DataFrame],
    pla_results: dict[tuple[str, str], pd.DataFrame],
    output: Path,
) -> None:
    ordered = sorted(signals.items())
    fig, axes = plt.subplots(
        len(ordered),
        2,
        figsize=(20, max(4 * len(ordered), 10)),
        sharex=True,
        squeeze=False,
        constrained_layout=True,
    )
    reference = max(signals.values(), key=len)
    for row, (joint_name, signal) in enumerate(ordered):
        for column, signal_name in enumerate(("velocity", "effort")):
            axis = axes[row, column]
            add_phase_background(axis, reference, labels=row == 0)
            plot_raw_and_pla(
                axis,
                signal,
                pla_results[(joint_name, signal_name)],
                signal_name,
                show_legend=row == 0,
            )
            style_axis(axis, SIGNAL_LABELS[signal_name])
            axis.set_title(f"{joint_name} {signal_name.title()} PLA")
    for axis in axes[-1, :]:
        axis.set_xlabel("Time since run start [s]")
    fig.suptitle(
        "Joint Velocity and Effort Piecewise Linear Approximations",
        fontsize=16,
    )
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)


def analyze_run(run_dir: Path, batch_output: Path) -> Path:
    output_dir = batch_output / run_dir.name
    csv_dir = output_dir / "csv"
    plots_dir = output_dir / "plots"
    csv_dir.mkdir(parents=True, exist_ok=False)
    plots_dir.mkdir(parents=True, exist_ok=False)

    signals: dict[str, pd.DataFrame] = {}
    for joint_csv in sorted(run_dir.glob("joint_*.csv"), key=natural_sort_key):
        try:
            signal = load_joint_signal(joint_csv)
            signals[str(signal["joint"].iloc[0])] = signal
        except (ValueError, pd.errors.EmptyDataError) as error:
            print(f"  Skipped {joint_csv.name}: {error}")
    if not signals:
        raise ValueError("no valid velocity and effort signals were loaded")

    run_start = min(float(signal["time_sec"].iloc[0]) for signal in signals.values())
    for signal in signals.values():
        signal["time_sec"] -= run_start

    pla_results: dict[tuple[str, str], pd.DataFrame] = {}
    for joint_name, signal in sorted(signals.items()):
        safe_name = joint_name.replace("/", "_").replace(" ", "_")
        for signal_name in ("velocity", "effort"):
            pla = merge_same_labels(build_pla_segments(signal, signal_name))
            if pla.empty:
                print(f"  No {signal_name} PLA segments for {joint_name}")
                continue
            pla_results[(joint_name, signal_name)] = pla
            pla.to_csv(csv_dir / f"{safe_name}_{signal_name}_PLA.csv", index=False)
            save_joint_pla_plot(
                signal,
                pla,
                signal_name,
                plots_dir / f"{safe_name}_{signal_name}_raw_and_PLA.png",
            )

    save_all_joints_plot(
        signals,
        pla_results,
        "velocity",
        plots_dir / "all_joint_velocities_raw_and_PLA_with_phases.png",
    )
    save_all_joints_plot(
        signals,
        pla_results,
        "effort",
        plots_dir / "all_joint_efforts_raw_and_PLA_with_phases.png",
    )
    save_velocity_effort_plot(
        signals,
        pla_results,
        plots_dir / "all_joint_velocities_and_efforts_raw_and_PLA_with_phases.png",
    )
    return output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create velocity and effort PLA CSVs and raw-data plots for every "
            "processed run, with phase shading and merged joint plots."
        )
    )
    parser.add_argument(
        "--processed-data-dir",
        type=Path,
        default=PROCESSED_DATA_DIR,
        help="Folder containing the processed run folders.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=OUTPUT_ROOT,
        help="Root folder for generated output batches.",
    )
    parser.add_argument(
        "--processed-run",
        type=Path,
        help="Process only this run folder instead of every run.",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        help="Process only the first N naturally sorted run folders.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_runs is not None and args.max_runs < 1:
        raise ValueError("--max-runs must be at least 1")

    if args.processed_run:
        runs = [args.processed_run.expanduser().resolve()]
    else:
        runs = find_processed_runs(args.processed_data_dir.expanduser().resolve())
        if args.max_runs is not None:
            runs = runs[: args.max_runs]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_output = args.output_root.expanduser().resolve() / f"batch_{timestamp}"
    batch_output.mkdir(parents=True, exist_ok=False)

    completed: list[Path] = []
    failed: list[tuple[Path, str]] = []
    print(f"Run folders selected: {len(runs)}")
    for number, run_dir in enumerate(runs, start=1):
        print(f"[{number}/{len(runs)}] Processing {run_dir.name}")
        try:
            completed.append(analyze_run(run_dir, batch_output))
        except (FileNotFoundError, ValueError) as error:
            failed.append((run_dir, str(error)))
            print(f"  Failed: {error}")

    print(f"Completed runs: {len(completed)}")
    print(f"Failed runs: {len(failed)}")
    print(f"Output batch: {batch_output}")
    for run_dir, reason in failed:
        print(f"  {run_dir.name}: {reason}")


if __name__ == "__main__":
    main()
