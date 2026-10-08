#!/usr/bin/env python3

"""
Franka Pick-and-Place Phase Segmentation

Segments demonstrations into:
    1. approach
    2. pick
    3. transport
    4. place
    5. retract

Detects gripper closing/opening using finger positions.

Supports:
    - Single CSV
    - Multiple CSV files in a directory
    - Automatic phase detection
    - Adjustable pick/place padding
    - CSV outputs with phase labels
    - Phase boundary summaries
    - Position and velocity plots

Note:
    Automatically detected phases are provisional.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# CONFIGURATION

PHASES = [
    "approach",
    "pick",
    "transport",
    "place",
    "retract",
]

PICK_BEFORE = 0.15
PICK_AFTER = 0.10

PLACE_BEFORE = 0.15
PLACE_AFTER = 0.10

SMOOTH_WINDOW = 5
GRIP_FRACTION = 0.20


# DETECT GRIPPER EVENTS


def detect_events(df):

    time = df["time_seconds"].to_numpy(dtype=float)

    finger_1 = df["finger_1_position"].to_numpy(dtype=float)
    finger_2 = df["finger_2_position"].to_numpy(dtype=float)

    fingers = (finger_1 + finger_2) / 2.0

    # Smooth finger movement
    finger_smooth = (
        pd.Series(fingers)
        .rolling(window=SMOOTH_WINDOW, center=True, min_periods=1)
        .median()
        .to_numpy()
    )

    high = np.nanpercentile(finger_smooth, 95)
    low = np.nanpercentile(finger_smooth, 5)

    spread = high - low

    if spread < 0.003:
        raise ValueError("No significant gripper opening/closing detected.")

    closed_threshold = high - GRIP_FRACTION * spread
    open_threshold = low + GRIP_FRACTION * spread

    indices = np.arange(len(df))

    # Detect closing

    close_start_candidates = np.where(finger_smooth < closed_threshold)[0]

    if len(close_start_candidates) == 0:
        raise ValueError("Gripper closing not detected.")

    close_start_idx = close_start_candidates[0]

    close_end_candidates = np.where(
        (indices >= close_start_idx) & (finger_smooth <= open_threshold)
    )[0]

    if len(close_end_candidates) == 0:
        raise ValueError("Gripper closure incomplete.")

    close_end_idx = close_end_candidates[0]

    # Detect opening

    open_start_candidates = np.where(
        (indices > close_end_idx) & (finger_smooth > open_threshold)
    )[0]

    if len(open_start_candidates) == 0:
        raise ValueError("Gripper opening not detected.")

    open_start_idx = open_start_candidates[0]

    open_end_candidates = np.where(
        (indices >= open_start_idx) & (finger_smooth >= closed_threshold)
    )[0]

    if len(open_end_candidates) == 0:
        raise ValueError("Gripper opening incomplete.")

    open_end_idx = open_end_candidates[0]

    if not (close_start_idx < close_end_idx < open_start_idx < open_end_idx < len(df)):
        raise ValueError("Invalid sequence of gripper events.")

    return [
        float(time[close_start_idx]),
        float(time[close_end_idx]),
        float(time[open_start_idx]),
        float(time[open_end_idx]),
    ]


# ADD SMALL PICK / PLACE PADDING


def expand_boundaries(
    raw_events,
    t_start,
    t_end,
    pick_before,
    pick_after,
    place_before,
    place_after,
):

    close_start, close_end, open_start, open_end = raw_events

    boundaries = [
        close_start - pick_before,
        close_end + pick_after,
        open_start - place_before,
        open_end + place_after,
    ]

    # All five phases must have positive duration.
    if not (
        t_start < boundaries[0] < boundaries[1] < boundaries[2] < boundaries[3] < t_end
    ):
        raise ValueError(
            "Phase boundaries overlap or exceed recording duration. "
            "Reduce the padding values."
        )

    return boundaries


# ASSIGN PHASE LABELS


def assign_phases(df, boundaries):

    time = df["time_seconds"].to_numpy(dtype=float)

    phase_indices = np.searchsorted(
        boundaries,
        time,
        side="right",
    )

    labeled_df = df.copy()

    # Remove an old phase column if present.
    if "phase" in labeled_df.columns:
        labeled_df = labeled_df.drop(columns=["phase"])

    labeled_df.insert(
        1,
        "phase",
        np.array(PHASES)[phase_indices],
    )

    return labeled_df


# CREATE PHASE SUMMARY


def create_phase_summary(df, labeled_df, boundaries):

    time_start = float(df["time_seconds"].iloc[0])
    time_end = float(df["time_seconds"].iloc[-1])

    starts = [time_start] + boundaries
    ends = boundaries + [time_end]

    summary = pd.DataFrame(
        {
            "phase": PHASES,
            "start_sec": starts,
            "end_sec": ends,
            "duration_sec": np.array(ends) - np.array(starts),
            "samples": [int((labeled_df["phase"] == phase).sum()) for phase in PHASES],
        }
    )

    return summary


# PLOT SEGMENTED SIGNALS


def plot_segmentation(df, boundaries, output_file):

    time = df["time_seconds"].to_numpy(dtype=float)

    spans = [
        float(time[0]),
        *boundaries,
        float(time[-1]),
    ]

    fig, axes = plt.subplots(
        4,
        1,
        figsize=(15, 13),
        sharex=True,
        constrained_layout=True,
    )

    # Arm joint positions

    for joint in range(1, 8):

        axes[0].plot(
            time,
            df[f"joint_{joint}_position"],
            linewidth=1,
            label=f"Joint {joint}",
        )

    axes[0].set_ylabel("Position (rad)")
    axes[0].set_title("Robot Joint Positions")
    axes[0].legend(ncol=7, fontsize=8)

    # Arm joint velocities

    for joint in range(1, 8):

        axes[1].plot(
            time,
            df[f"joint_{joint}_velocity"],
            linewidth=1,
            label=f"Joint {joint}",
        )

    axes[1].set_ylabel("Velocity (rad/s)")
    axes[1].set_title("Robot Joint Velocities")

    # Finger positions

    for finger in (1, 2):

        axes[2].plot(
            time,
            df[f"finger_{finger}_position"],
            linewidth=1.5,
            label=f"Finger {finger}",
        )

    axes[2].set_ylabel("Finger position")
    axes[2].set_title("Gripper Finger Positions")
    axes[2].legend()

    # Finger velocities

    for finger in (1, 2):

        axes[3].plot(
            time,
            df[f"finger_{finger}_velocity"],
            linewidth=1.5,
            label=f"Finger {finger}",
        )

    axes[3].set_ylabel("Finger velocity")
    axes[3].set_title("Gripper Finger Velocities")
    axes[3].set_xlabel("Elapsed Time (seconds)")
    axes[3].legend()

    # Display phase regions

    colors = [
        "#d9eaf7",
        "#fce8b2",
        "#d9ead3",
        "#eadcf8",
        "#f4cccc",
    ]

    for ax in axes:

        for i, phase in enumerate(PHASES):

            ax.axvspan(
                spans[i],
                spans[i + 1],
                color=colors[i],
                alpha=0.35,
            )

            ax.axvline(
                spans[i],
                color="gray",
                linestyle="--",
                linewidth=0.7,
            )

        ax.grid(alpha=0.3)

    for i, phase in enumerate(PHASES):

        center = (spans[i] + spans[i + 1]) / 2

        axes[0].text(
            center,
            1.02,
            phase.capitalize(),
            ha="center",
            transform=axes[0].get_xaxis_transform(),
            fontsize=9,
        )

    fig.savefig(
        output_file,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(fig)


# PROCESS ONE DEMONSTRATION


def process_demo(csv_file, output_dir, args):

    df = pd.read_csv(csv_file)

    required_columns = ["time_seconds"]

    for joint in range(1, 8):

        required_columns.extend(
            [
                f"joint_{joint}_position",
                f"joint_{joint}_velocity",
            ]
        )

    for finger in (1, 2):

        required_columns.extend(
            [
                f"finger_{finger}_position",
                f"finger_{finger}_velocity",
            ]
        )

    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        raise ValueError(f"Missing columns: {missing}")

    if df[required_columns].isna().any().any():
        raise ValueError("Required columns contain missing values.")

    df = df.sort_values("time_seconds").reset_index(drop=True)

    time = df["time_seconds"].to_numpy(dtype=float)

    if not np.isfinite(df[required_columns].to_numpy(dtype=float)).all():
        raise ValueError("Required columns contain non-finite values.")

    if np.any(np.diff(time) <= 0):
        raise ValueError("Time values must be strictly increasing.")

    # Detect gripper events

    raw_events = detect_events(df)

    # Expand pick and place

    boundaries = expand_boundaries(
        raw_events,
        t_start=float(time[0]),
        t_end=float(time[-1]),
        pick_before=args.pick_before,
        pick_after=args.pick_after,
        place_before=args.place_before,
        place_after=args.place_after,
    )

    # Assign phase labels

    labeled_df = assign_phases(df, boundaries)

    summary = create_phase_summary(
        df,
        labeled_df,
        boundaries,
    )

    demo_name = csv_file.stem

    labeled_file = output_dir / f"{demo_name}_labeled.csv"

    summary_file = output_dir / f"{demo_name}_phase_boundaries.csv"

    plot_file = output_dir / f"{demo_name}_phases.png"

    labeled_df.to_csv(labeled_file, index=False)

    summary.to_csv(summary_file, index=False)

    plot_segmentation(
        df,
        boundaries,
        plot_file,
    )

    print(f"\nDemonstration: {demo_name}")
    print(summary.to_string(index=False))

    summary.insert(0, "demonstration", demo_name)

    return summary


# MAIN


def main():

    parser = argparse.ArgumentParser(
        description="Franka pick-and-place phase segmentation."
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Single CSV file or folder containing CSVs",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "segmented",
    )

    parser.add_argument(
        "--pick-before",
        type=float,
        default=PICK_BEFORE,
    )

    parser.add_argument(
        "--pick-after",
        type=float,
        default=PICK_AFTER,
    )

    parser.add_argument(
        "--place-before",
        type=float,
        default=PLACE_BEFORE,
    )

    parser.add_argument(
        "--place-after",
        type=float,
        default=PLACE_AFTER,
    )

    args = parser.parse_args()

    for name in (
        "pick_before",
        "pick_after",
        "place_before",
        "place_after",
    ):
        if getattr(args, name) < 0:
            parser.error(f"--{name.replace('_', '-')} must be nonnegative")

    input_path = args.input
    output_dir = args.output

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    if input_path.is_dir():

        csv_files = sorted(input_path.glob("*.csv"))

        # Avoid processing previously labeled outputs.
        csv_files = [
            path
            for path in csv_files
            if not path.stem.endswith("_labeled")
            and not path.stem.endswith("_phase_boundaries")
            and path.name != "all_phase_boundaries.csv"
        ]

    else:
        csv_files = [input_path]

    if not csv_files:
        parser.error("No CSV files found.")

    all_summaries = []
    processed = 0

    for csv_file in csv_files:

        try:

            summary = process_demo(
                csv_file,
                output_dir,
                args,
            )

            all_summaries.append(summary)
            processed += 1

        except (ValueError, KeyError, OSError) as error:

            print(f"\nSKIPPED {csv_file.name}: {error}")

    if all_summaries:

        combined = pd.concat(
            all_summaries,
            ignore_index=True,
        )

        combined.to_csv(
            output_dir / "all_phase_boundaries.csv",
            index=False,
        )

    print("\n===================================")
    print("SEGMENTATION COMPLETED")
    print("===================================")

    print(f"Total files: {len(csv_files)}")
    print(f"Successfully processed: {processed}")
    print(f"Skipped: {len(csv_files) - processed}")
    print(f"Output directory: {output_dir}")
    if processed != len(csv_files):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
