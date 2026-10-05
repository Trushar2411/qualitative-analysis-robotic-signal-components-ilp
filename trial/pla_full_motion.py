#!/usr/bin/env python3

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# CONFIGURATION
# ============================================================

WINDOW_SIZE = 5
STEP_SIZE = 5

# Threshold = minimum fitted change across one PLA window
# required to call the window ramp_up / ramp_down.
#
# You may tune these later depending on the scale/noise of
# your xArm signals.
THRESHOLDS = {
    "position": 0.005,
    "velocity": 0.010,
    "effort": 0.050,
}

SIGNAL_TYPES = ["position", "velocity", "effort"]

JOINTS = [1, 2, 3, 4, 5, 6]


# ============================================================
# PLA CLASSIFICATION
# ============================================================

def classify_change(change, threshold):
    """
    Convert fitted change over one PLA window into a
    qualitative label.
    """

    if change > threshold:
        return "ramp_up"

    elif change < -threshold:
        return "ramp_down"

    else:
        return "constant"


# ============================================================
# FIND PHASE COLUMN
# ============================================================

def find_phase_column(df):
    """
    Try to automatically find the phase column.
    """

    possible_names = [
        "phase",
        "Phase",
        "PHASE",
        "motion_phase",
        "Motion_Phase",
        "label",
        "Label",
    ]

    for col in possible_names:
        if col in df.columns:
            return col

    raise ValueError(
        "\nCould not find a phase column.\n"
        f"Available columns:\n{list(df.columns)}\n\n"
        "Rename your phase column to 'phase' or add its name "
        "inside find_phase_column()."
    )


# ============================================================
# FIND TIME COLUMN
# ============================================================

def get_time_array(df):
    """
    Use bag_time_sec if available.

    Otherwise use sample number.
    """

    possible_time_columns = [
        "bag_time_sec",
        "time",
        "timestamp",
        "Time",
        "Timestamp",
    ]

    for col in possible_time_columns:

        if col in df.columns:

            t = pd.to_numeric(
                df[col],
                errors="coerce"
            ).to_numpy(dtype=float)

            # Relative time
            t = t - t[0]

            return t, col

    print(
        "WARNING: No time column found. "
        "Using sample index instead."
    )

    return np.arange(len(df), dtype=float), None


# ============================================================
# GET JOINT COLUMNS
# ============================================================

def get_joint_columns(df, signal_type):
    """
    Expected format:

    joint1_position
    joint2_position
    ...

    joint1_velocity
    ...

    joint1_effort
    ...
    """

    columns = [
        f"joint{i}_{signal_type}"
        for i in JOINTS
    ]

    missing = [
        col
        for col in columns
        if col not in df.columns
    ]

    if missing:

        raise ValueError(
            f"\nMissing {signal_type} columns:\n"
            f"{missing}\n\n"
            f"Available columns:\n"
            f"{list(df.columns)}"
        )

    return columns


# ============================================================
# RUN PLA FOR ONE COMPLETE PHASE
# ============================================================

def run_pla_on_phase(
    phase_df,
    signal_type,
    signal_columns,
    time_values,
    threshold,
):
    """
    Run sliding-window PLA inside ONE phase.

    Important:
    Windows never cross phase boundaries.

    WINDOW_SIZE = 10
    STEP_SIZE   = 5

    Returns:
        detailed window-level PLA results
    """

    results = []

    number_of_samples = len(phase_df)

    if number_of_samples < WINDOW_SIZE:

        print(
            f"WARNING: Phase has only "
            f"{number_of_samples} samples. "
            f"PLA window requires {WINDOW_SIZE}."
        )

        return pd.DataFrame()

    # --------------------------------------------------------
    # Sliding PLA windows
    # --------------------------------------------------------

    for start in range(
        0,
        number_of_samples - WINDOW_SIZE + 1,
        STEP_SIZE,
    ):

        end = start + WINDOW_SIZE

        t = time_values[start:end]

        result = {
            "window_start": start,
            "window_end": end - 1,
        }

        # ----------------------------------------------------
        # Fit every joint
        # ----------------------------------------------------

        for col in signal_columns:

            y = pd.to_numeric(
                phase_df[col].iloc[start:end],
                errors="coerce",
            ).to_numpy(dtype=float)

            valid = (
                np.isfinite(t)
                &
                np.isfinite(y)
            )

            # Not enough valid points
            if valid.sum() < 2:

                slope = 0.0
                fitted_change = 0.0
                label = "constant"

            else:

                tv = t[valid]
                yv = y[valid]

                # --------------------------------------------
                # Linear regression
                #
                # y = slope * t + intercept
                # --------------------------------------------

                slope, intercept = np.polyfit(
                    tv,
                    yv,
                    1,
                )

                # --------------------------------------------
                # Change predicted by PLA across this window
                # --------------------------------------------

                duration = tv[-1] - tv[0]

                # If timestamp is identical, use sample span
                if duration == 0:
                    duration = len(tv) - 1

                fitted_change = slope * duration

                # --------------------------------------------
                # Qualitative classification
                # --------------------------------------------

                label = classify_change(
                    fitted_change,
                    threshold,
                )

            result[f"{col}_slope"] = slope
            result[f"{col}_change"] = fitted_change
            result[f"{col}_label"] = label

        results.append(result)

    return pd.DataFrame(results)


# ============================================================
# MAJORITY PLA LABEL FOR WHOLE PHASE
# ============================================================

def get_phase_average_label(
    window_results,
    signal_columns,
):
    """
    Find the dominant PLA classification for each joint
    across the complete phase.

    Example:

        Joint 2 during approach:

        ramp_up    = 8 windows
        ramp_down  = 1 window
        constant   = 2 windows

        Final phase classification:

        joint2 = ramp_up

    This is a categorical majority/mode, not a numerical mean.
    """

    phase_result = {}

    for col in signal_columns:

        label_col = f"{col}_label"

        labels = window_results[label_col].dropna()

        if len(labels) == 0:

            phase_result[col] = "unknown"

            continue

        counts = labels.value_counts()

        # Dominant qualitative behaviour
        dominant_label = counts.idxmax()

        phase_result[col] = dominant_label

        # Also save counts
        phase_result[f"{col}_ramp_up_count"] = int(
            counts.get("ramp_up", 0)
        )

        phase_result[f"{col}_ramp_down_count"] = int(
            counts.get("ramp_down", 0)
        )

        phase_result[f"{col}_constant_count"] = int(
            counts.get("constant", 0)
        )

        phase_result[f"{col}_total_windows"] = len(labels)

    return phase_result


# ============================================================
# PROCESS ONE SIGNAL TYPE
# ============================================================

def process_signal_type(
    df,
    phase_col,
    full_time,
    signal_type,
    output_dir,
):
    """
    Process position / velocity / effort independently.
    """

    threshold = THRESHOLDS[signal_type]

    signal_columns = get_joint_columns(
        df,
        signal_type,
    )

    phase_summary_rows = []

    all_window_results = []

    # Preserve original phase order
    phases = df[phase_col].dropna().unique()

    print()
    print("=" * 70)
    print(f"Processing {signal_type.upper()}")
    print("=" * 70)

    for phase in phases:

        # ----------------------------------------------------
        # Select complete phase
        # ----------------------------------------------------

        phase_mask = df[phase_col] == phase

        phase_df = df.loc[
            phase_mask
        ].reset_index(drop=True)

        phase_time = full_time[phase_mask.to_numpy()]

        # Make phase time relative to phase start
        if len(phase_time) > 0:
            phase_time = phase_time - phase_time[0]

        print(
            f"\nPhase: {phase}"
            f" | samples: {len(phase_df)}"
        )

        # ----------------------------------------------------
        # Run PLA inside this phase
        # ----------------------------------------------------

        window_results = run_pla_on_phase(
            phase_df=phase_df,
            signal_type=signal_type,
            signal_columns=signal_columns,
            time_values=phase_time,
            threshold=threshold,
        )

        if window_results.empty:

            print(
                f"Skipping phase '{phase}' "
                f"because it is shorter than window size."
            )

            continue

        # ----------------------------------------------------
        # Save phase name to detailed results
        # ----------------------------------------------------

        window_results.insert(
            0,
            "phase",
            phase,
        )

        all_window_results.append(
            window_results
        )

        # ----------------------------------------------------
        # Get dominant behaviour of each joint
        # ----------------------------------------------------

        phase_result = get_phase_average_label(
            window_results,
            signal_columns,
        )

        summary = {
            "phase": phase,
        }

        # ----------------------------------------------------
        # Simple six-joint output
        # ----------------------------------------------------

        for joint_number, col in zip(
            JOINTS,
            signal_columns,
        ):

            summary[f"joint{joint_number}"] = (
                phase_result[col]
            )

        # ----------------------------------------------------
        # Add detailed counts
        # ----------------------------------------------------

        for joint_number, col in zip(
            JOINTS,
            signal_columns,
        ):

            summary[
                f"joint{joint_number}_ramp_up_count"
            ] = phase_result[
                f"{col}_ramp_up_count"
            ]

            summary[
                f"joint{joint_number}_ramp_down_count"
            ] = phase_result[
                f"{col}_ramp_down_count"
            ]

            summary[
                f"joint{joint_number}_constant_count"
            ] = phase_result[
                f"{col}_constant_count"
            ]

            summary[
                f"joint{joint_number}_total_windows"
            ] = phase_result[
                f"{col}_total_windows"
            ]

        phase_summary_rows.append(summary)

        # ----------------------------------------------------
        # Print result
        # ----------------------------------------------------

        print("Phase-average PLA:")

        for joint_number, col in zip(
            JOINTS,
            signal_columns,
        ):

            print(
                f"  Joint {joint_number}: "
                f"{phase_result[col]}"
            )

    # ========================================================
    # FINAL PHASE SUMMARY
    # ========================================================

    summary_df = pd.DataFrame(
        phase_summary_rows
    )

    summary_file = (
        output_dir
        /
        f"pla_{signal_type}_phase_summary.csv"
    )

    summary_df.to_csv(
        summary_file,
        index=False,
    )

    # ========================================================
    # DETAILED WINDOW RESULTS
    # ========================================================

    if all_window_results:

        detailed_df = pd.concat(
            all_window_results,
            ignore_index=True,
        )

        detailed_file = (
            output_dir
            /
            f"pla_{signal_type}_windows.csv"
        )

        detailed_df.to_csv(
            detailed_file,
            index=False,
        )

    else:

        detailed_df = pd.DataFrame()

    print(
        f"\nSaved phase summary:\n"
        f"{summary_file}"
    )

    return summary_df, detailed_df


# ============================================================
# PLOT ORIGINAL SIGNALS WITH PHASE BOUNDARIES
# ============================================================

def plot_signal(
    df,
    phase_col,
    full_time,
    signal_type,
    output_dir,
):
    """
    Create one plot for each signal type.

    Shows all six joints and phase boundaries.
    """

    signal_columns = get_joint_columns(
        df,
        signal_type,
    )

    fig, ax = plt.subplots(
        figsize=(16, 8)
    )

    # --------------------------------------------------------
    # Plot six joints
    # --------------------------------------------------------

    for col in signal_columns:

        values = pd.to_numeric(
            df[col],
            errors="coerce",
        )

        ax.plot(
            full_time,
            values,
            linewidth=1.2,
            label=col,
        )

    # --------------------------------------------------------
    # Phase boundaries
    # --------------------------------------------------------

    phase_values = df[phase_col].astype(str)

    changes = (
        phase_values
        !=
        phase_values.shift()
    )

    phase_start_indices = np.where(
        changes
    )[0]

    y_min, y_max = ax.get_ylim()

    for index in phase_start_indices:

        x = full_time[index]

        ax.axvline(
            x=x,
            linestyle="--",
            linewidth=1,
            alpha=0.5,
        )

        phase_name = phase_values.iloc[index]

        ax.text(
            x,
            y_max,
            str(phase_name),
            rotation=90,
            verticalalignment="top",
            fontsize=8,
        )

    # --------------------------------------------------------
    # Formatting
    # --------------------------------------------------------

    ax.set_title(
        f"xArm6 Joint {signal_type.capitalize()}\n"
        f"PLA Window = {WINDOW_SIZE}, "
        f"Step = {STEP_SIZE}"
    )

    ax.set_xlabel(
        "Time from motion start"
    )

    if signal_type == "position":

        ax.set_ylabel(
            "Joint Position"
        )

    elif signal_type == "velocity":

        ax.set_ylabel(
            "Joint Velocity"
        )

    else:

        ax.set_ylabel(
            "Joint Effort"
        )

    ax.grid(
        True,
        alpha=0.25,
    )

    ax.legend(
        ncol=2,
        fontsize=9,
    )

    fig.tight_layout()

    output_file = (
        output_dir
        /
        f"pla_{signal_type}.png"
    )

    fig.savefig(
        output_file,
        dpi=200,
    )

    plt.close(fig)

    print(
        f"Saved plot:\n"
        f"{output_file}"
    )


# ============================================================
# PRINT FINAL SUMMARY
# ============================================================

def print_final_summary(
    summary_df,
    signal_type,
):
    """
    Print only phase + six joint labels.
    """

    print()
    print("=" * 70)
    print(
        f"{signal_type.upper()} "
        f"PHASE SUMMARY"
    )
    print("=" * 70)

    display_columns = [
        "phase",
        "joint1",
        "joint2",
        "joint3",
        "joint4",
        "joint5",
        "joint6",
    ]

    print(
        summary_df[
            display_columns
        ].to_string(
            index=False
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Small-window PLA followed by "
            "phase-level qualitative aggregation "
            "for xArm6 joint signals."
        )
    )

    parser.add_argument(
        "csv_file",
        help="Full-motion joint-state CSV file",
    )

    parser.add_argument(
        "--output-dir",
        default="pla_output",
        help=(
            "Directory for output files "
            "(default: pla_output)"
        ),
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # Input / output
    # --------------------------------------------------------

    input_file = Path(
        args.csv_file
    )

    output_dir = Path(
        args.output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Read CSV
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PLA ANALYSIS")
    print("=" * 70)

    print(
        f"\nInput file:\n{input_file}"
    )

    df = pd.read_csv(
        input_file
    )

    print(
        f"\nNumber of samples: "
        f"{len(df)}"
    )

    print(
        f"Window size: {WINDOW_SIZE}"
    )

    print(
        f"Step size: {STEP_SIZE}"
    )

    # --------------------------------------------------------
    # Phase column
    # --------------------------------------------------------

    phase_col = find_phase_column(
        df
    )

    print(
        f"Phase column: {phase_col}"
    )

    print(
        "Phases:",
        list(
            df[phase_col]
            .dropna()
            .unique()
        ),
    )

    # --------------------------------------------------------
    # Time
    # --------------------------------------------------------

    full_time, time_col = get_time_array(
        df
    )

    if time_col:

        print(
            f"Time column: {time_col}"
        )

    # ========================================================
    # POSITION
    # ========================================================

    position_summary, _ = process_signal_type(
        df=df,
        phase_col=phase_col,
        full_time=full_time,
        signal_type="position",
        output_dir=output_dir,
    )

    plot_signal(
        df=df,
        phase_col=phase_col,
        full_time=full_time,
        signal_type="position",
        output_dir=output_dir,
    )

    # ========================================================
    # VELOCITY
    # ========================================================

    velocity_summary, _ = process_signal_type(
        df=df,
        phase_col=phase_col,
        full_time=full_time,
        signal_type="velocity",
        output_dir=output_dir,
    )

    plot_signal(
        df=df,
        phase_col=phase_col,
        full_time=full_time,
        signal_type="velocity",
        output_dir=output_dir,
    )

    # ========================================================
    # EFFORT
    # ========================================================

    effort_summary, _ = process_signal_type(
        df=df,
        phase_col=phase_col,
        full_time=full_time,
        signal_type="effort",
        output_dir=output_dir,
    )

    plot_signal(
        df=df,
        phase_col=phase_col,
        full_time=full_time,
        signal_type="effort",
        output_dir=output_dir,
    )

    # ========================================================
    # PRINT CLEAN FINAL RESULTS
    # ========================================================

    print_final_summary(
        position_summary,
        "position",
    )

    print_final_summary(
        velocity_summary,
        "velocity",
    )

    print_final_summary(
        effort_summary,
        "effort",
    )

    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)

    print(
        f"""
Results are available in:

{output_dir}/

Main phase-level CSV files:

    pla_position_phase_summary.csv
    pla_velocity_phase_summary.csv
    pla_effort_phase_summary.csv

Detailed PLA-window CSV files:

    pla_position_windows.csv
    pla_velocity_windows.csv
    pla_effort_windows.csv

Plots:

    pla_position.png
    pla_velocity.png
    pla_effort.png

PLA configuration:

    WINDOW_SIZE = {WINDOW_SIZE}
    STEP_SIZE   = {STEP_SIZE}

Labels:

    ramp_up
    ramp_down
    constant
"""
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
