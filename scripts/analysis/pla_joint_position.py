from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DATA_DIR = REPO_ROOT / "Processed data"
OUTPUT_ROOT = REPO_ROOT / "outputs" / "PLA_position"

WINDOW_SIZE = 20
STEP = 20
PLA_SEGMENTS = 4

# Position slope has units of position/second. If joint position is stored in
# radians, this threshold is rad/s.
DIRECTION_THRESHOLD = 0.02

PHASE_COLORS = {
    "home": "#d9eaf7",
    "pick": "#fce8b2",
    "lift": "#d9ead3",
    "place": "#eadcf8",
    "retract": "#f4cccc",
    "unknown": "#eeeeee",
}


def find_processed_runs(
    processed_data_dir: Path = PROCESSED_DATA_DIR,
) -> list[Path]:
    if not processed_data_dir.exists():
        raise FileNotFoundError(
            f"Processed data folder not found: {processed_data_dir}"
        )

    runs = sorted(
        [
            path
            for path in processed_data_dir.iterdir()
            if path.is_dir() and any(path.glob("joint_*.csv"))
        ],
        key=lambda path: path.name.lower(),
    )

    if not runs:
        raise FileNotFoundError(
            f"No run folders containing joint_*.csv were found in "
            f"{processed_data_dir}"
        )

    return runs


def load_joint_signal(joint_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(joint_csv)

    required_columns = [
        "joint",
        "bag_time_sec",
        "position",
        "phase",
    ]

    missing_columns = [
        column for column in required_columns if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"{joint_csv} is missing: {', '.join(missing_columns)}"
        )

    signal = df[required_columns].copy()
    signal["bag_time_sec"] = pd.to_numeric(
        signal["bag_time_sec"], errors="coerce"
    )
    signal["position"] = pd.to_numeric(
        signal["position"], errors="coerce"
    )

    signal = signal.dropna(subset=["bag_time_sec", "position"])
    signal = signal.rename(columns={"bag_time_sec": "time_sec"})
    signal = signal[
        np.isfinite(signal["time_sec"])
        & np.isfinite(signal["position"])
    ]
    signal = signal.sort_values("time_sec").reset_index(drop=True)

    if len(signal) < WINDOW_SIZE:
        raise ValueError(
            f"{joint_csv} needs at least {WINDOW_SIZE} valid samples."
        )

    signal["phase"] = signal["phase"].fillna("unknown").astype(str)
    return signal


def direction_label(slope: float) -> str:
    if slope > DIRECTION_THRESHOLD:
        return "ramp_up"
    if slope < -DIRECTION_THRESHOLD:
        return "ramp_down"
    return "constant"


def dominant_phase(phases: pd.Series) -> str:
    valid_phases = phases.dropna()
    if valid_phases.empty:
        return "unknown"
    return str(valid_phases.value_counts().idxmax())


def build_pla_segments(signal: pd.DataFrame) -> pd.DataFrame:
    time_values = signal["time_sec"].to_numpy(dtype=float)
    position_values = signal["position"].to_numpy(dtype=float)
    joint_name = str(signal["joint"].iloc[0])

    rows: list[dict[str, object]] = []
    segment_id = 0

    for start in range(
        0,
        len(position_values) - WINDOW_SIZE + 1,
        STEP,
    ):
        end = start + WINDOW_SIZE
        window_indices = np.arange(start, end)
        segment_indices = np.array_split(window_indices, PLA_SEGMENTS)

        for indices in segment_indices:
            if len(indices) < 2:
                continue

            time_segment = time_values[indices]
            position_segment = position_values[indices]
            slope, intercept = np.polyfit(
                time_segment,
                position_segment,
                1,
            )

            rows.append(
                {
                    "segment_id": segment_id,
                    "joint": joint_name,
                    "start_time_sec": float(time_segment[0]),
                    "end_time_sec": float(time_segment[-1]),
                    "duration_sec": float(
                        time_segment[-1] - time_segment[0]
                    ),
                    "phase": dominant_phase(signal.iloc[indices]["phase"]),
                    "label": direction_label(float(slope)),
                    "slope": float(slope),
                    "intercept": float(intercept),
                    "start_position": float(position_segment[0]),
                    "end_position": float(position_segment[-1]),
                    "mean_position": float(np.mean(position_segment)),
                }
            )
            segment_id += 1

    return pd.DataFrame(rows)


def merge_same_labels(pla_df: pd.DataFrame) -> pd.DataFrame:
    if pla_df.empty:
        return pla_df

    merged_rows: list[dict[str, object]] = []
    current = pla_df.iloc[0].to_dict()

    for _, next_row in pla_df.iloc[1:].iterrows():
        row = next_row.to_dict()
        same_label = row["label"] == current["label"]
        same_phase = row["phase"] == current["phase"]

        if same_label and same_phase:
            current["end_time_sec"] = row["end_time_sec"]
            current["duration_sec"] = (
                current["end_time_sec"] - current["start_time_sec"]
            )
            current["end_position"] = row["end_position"]
            current["mean_position"] = (
                current["start_position"] + current["end_position"]
            ) / 2.0
            current["slope"] = (
                current["end_position"] - current["start_position"]
            ) / max(current["duration_sec"], 1e-9)
            current["intercept"] = (
                current["start_position"]
                - current["slope"] * current["start_time_sec"]
            )
        else:
            merged_rows.append(current)
            current = row

    merged_rows.append(current)
    merged_df = pd.DataFrame(merged_rows)
    merged_df["segment_id"] = range(len(merged_df))
    return merged_df


def get_phase_intervals(signal: pd.DataFrame) -> list[tuple[float, float, str]]:
    if signal.empty:
        return []

    phase_values = signal["phase"].fillna("unknown").astype(str).to_numpy()
    time_values = signal["time_sec"].to_numpy(dtype=float)
    change_indices = np.flatnonzero(phase_values[1:] != phase_values[:-1]) + 1
    boundaries = np.concatenate(([0], change_indices, [len(signal)]))

    intervals: list[tuple[float, float, str]] = []
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        start_time = float(time_values[left])
        end_time = float(time_values[right - 1])
        phase = str(phase_values[left])
        intervals.append((start_time, end_time, phase))

    return intervals


def add_phase_background(axis: plt.Axes, signal: pd.DataFrame) -> None:
    for start_time, end_time, phase in get_phase_intervals(signal):
        color = PHASE_COLORS.get(phase.lower(), "#eeeeee")
        axis.axvspan(
            start_time,
            end_time,
            color=color,
            alpha=0.28,
            linewidth=0,
            zorder=0,
        )

        if end_time > start_time:
            axis.text(
                (start_time + end_time) / 2.0,
                0.98,
                phase.replace("_", " ").title(),
                transform=axis.get_xaxis_transform(),
                ha="center",
                va="top",
                fontsize=9,
                color="0.25",
            )


def save_joint_plot(
    signal: pd.DataFrame,
    pla_df: pd.DataFrame,
    out_plot: Path,
) -> None:
    out_plot.parent.mkdir(parents=True, exist_ok=True)

    time_values = signal["time_sec"].to_numpy(dtype=float)
    position_values = signal["position"].to_numpy(dtype=float)
    joint_name = str(signal["joint"].iloc[0])

    colors = {
        "ramp_up": "tab:green",
        "ramp_down": "tab:red",
        "constant": "tab:blue",
    }

    fig, axis = plt.subplots(figsize=(14, 7), constrained_layout=True)
    add_phase_background(axis, signal)

    axis.plot(
        time_values,
        position_values,
        color="0.55",
        linewidth=1.2,
        label="Raw position",
        zorder=2,
    )

    labels_added: set[str] = set()
    for _, row in pla_df.iterrows():
        start_time = float(row["start_time_sec"])
        end_time = float(row["end_time_sec"])
        mask = (time_values >= start_time) & (time_values <= end_time)
        segment_time = time_values[mask]
        segment_position = position_values[mask]

        if len(segment_time) < 2:
            continue

        slope, intercept = np.polyfit(
            segment_time,
            segment_position,
            1,
        )
        fitted_position = slope * segment_time + intercept
        label = str(row["label"])
        legend_label = (
            label.replace("_", " ").title()
            if label not in labels_added
            else None
        )

        axis.plot(
            segment_time,
            fitted_position,
            color=colors.get(label, "black"),
            linewidth=2.5,
            label=legend_label,
            zorder=3,
        )
        labels_added.add(label)

    axis.set_title(
        f"{joint_name} Position Piecewise Linear Approximation",
        fontsize=15,
    )
    axis.set_xlabel("Time since run start [s]")
    axis.set_ylabel("Joint position [rad]")
    axis.grid(True, linestyle="--", alpha=0.4)
    axis.axhline(y=0, color="black", linewidth=0.8, alpha=0.6)
    axis.legend(loc="best")

    fig.savefig(out_plot, dpi=300, bbox_inches="tight")
    plt.close(fig)


def save_all_joints_plot(
    signals: dict[str, pd.DataFrame],
    out_plot: Path,
) -> None:
    out_plot.parent.mkdir(parents=True, exist_ok=True)

    fig, axis = plt.subplots(figsize=(16, 8), constrained_layout=True)

    # Use the signal with the most samples as the phase timeline. The phase
    # timestamps should be shared by all joint CSV files from the same run.
    phase_reference = max(signals.values(), key=len)
    add_phase_background(axis, phase_reference)

    color_map = plt.get_cmap("tab10")
    for index, (joint_name, signal) in enumerate(sorted(signals.items())):
        axis.plot(
            signal["time_sec"],
            signal["position"],
            linewidth=1.6,
            color=color_map(index % 10),
            label=joint_name,
            zorder=2,
        )

    axis.set_title("All Joint Positions with Motion Phases", fontsize=15)
    axis.set_xlabel("Time since run start [s]")
    axis.set_ylabel("Joint position [rad]")
    axis.grid(True, linestyle="--", alpha=0.4)
    axis.axhline(y=0, color="black", linewidth=0.8, alpha=0.6)
    axis.legend(loc="best", ncol=2)

    fig.savefig(out_plot, dpi=300, bbox_inches="tight")
    plt.close(fig)


def analyze_run(processed_run_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_ROOT / (
        f"{processed_run_dir.name}_PLA_position_{timestamp}"
    )
    csv_dir = output_dir / "csv"
    plots_dir = output_dir / "plots"
    csv_dir.mkdir(parents=True, exist_ok=False)
    plots_dir.mkdir(parents=True, exist_ok=False)

    joint_csv_files = sorted(processed_run_dir.glob("joint_*.csv"))
    if not joint_csv_files:
        raise FileNotFoundError(
            f"No joint_*.csv files found in {processed_run_dir}"
        )

    signals: dict[str, pd.DataFrame] = {}

    # Load all files first so every joint can use the same run start time.
    for joint_csv in joint_csv_files:
        try:
            signal = load_joint_signal(joint_csv)
            joint_name = str(signal["joint"].iloc[0])
            signals[joint_name] = signal
        except (ValueError, pd.errors.EmptyDataError) as error:
            print(f"Skipped {joint_csv.name}: {error}")

    if not signals:
        raise ValueError("No valid joint position signals were loaded.")

    global_start_time = min(
        float(signal["time_sec"].iloc[0]) for signal in signals.values()
    )
    for signal in signals.values():
        signal["time_sec"] = signal["time_sec"] - global_start_time

    for joint_name, signal in sorted(signals.items()):
        print(f"Processing: {joint_name}")
        initial_pla_df = build_pla_segments(signal)
        pla_df = merge_same_labels(initial_pla_df)

        if pla_df.empty:
            print(f"  Skipped {joint_name}: no PLA segments were generated.")
            continue

        safe_joint_name = joint_name.replace("/", "_").replace(" ", "_")
        output_csv = csv_dir / f"{safe_joint_name}_position_PLA.csv"
        output_plot = plots_dir / f"{safe_joint_name}_position_PLA.png"

        pla_df.to_csv(output_csv, index=False)
        save_joint_plot(signal, pla_df, output_plot)

        print(f"  CSV saved: {output_csv}")
        print(f"  Plot saved: {output_plot}")

    combined_plot = plots_dir / "all_joints_position_with_phases.png"
    save_all_joints_plot(signals, combined_plot)
    print(f"Combined plot saved: {combined_plot}")

    return output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run piecewise linear approximation on processed joint "
            "position data and plot all joints together."
        )
    )
    parser.add_argument(
        "--processed-run",
        type=Path,
        default=None,
        help=(
            "Path to a Processed data run folder. "
            "If omitted, every valid run folder inside Processed data "
            "is processed."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.processed_run is not None:
        processed_run_dirs = [args.processed_run.expanduser().resolve()]
    else:
        processed_run_dirs = find_processed_runs()

    output_dirs: list[Path] = []
    failed_runs: list[tuple[Path, str]] = []

    print(f"Run folders found: {len(processed_run_dirs)}")

    for run_number, processed_run_dir in enumerate(
        processed_run_dirs,
        start=1,
    ):
        print()
        print(
            f"[{run_number}/{len(processed_run_dirs)}] "
            f"Processing run: {processed_run_dir.name}"
        )

        if not processed_run_dir.exists():
            failed_runs.append(
                (processed_run_dir, "folder does not exist")
            )
            print(f"Skipped: folder not found: {processed_run_dir}")
            continue

        try:
            output_dir = analyze_run(processed_run_dir)
            output_dirs.append(output_dir)
        except (FileNotFoundError, ValueError) as error:
            failed_runs.append((processed_run_dir, str(error)))
            print(f"Skipped run: {error}")

    print()
    print(f"Successfully processed runs: {len(output_dirs)}")
    for output_dir in output_dirs:
        print(f"  {output_dir}")

    if failed_runs:
        print(f"Skipped or failed runs: {len(failed_runs)}")
        for run_dir, reason in failed_runs:
            print(f"  {run_dir.name}: {reason}")


if __name__ == "__main__":
    main()
