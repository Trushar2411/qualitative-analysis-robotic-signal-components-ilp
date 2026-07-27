#!/usr/bin/env python3
"""
QTA Visualizer for Robile Wall Following Data
=============================================
This script:
1. Reads cleaned CSV files (from event detection)
2. Applies QTA per action window
3. Creates visualization graphs like Trushar's PLA
4. Saves QTA results as JSON for ILP use

Author: Alisha Syed Karimulla
Project: Qualitative Analysis of Robotic Signal
         Components using ILP
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import os
import json


# ── CONFIGURATION ─────────────────────────────────────────────

# Input folder (cleaned CSV files from event detection)
INPUT_DIR  = os.path.expanduser(
    '~/rnd_ws/data_cleaned')

# Output folders
PLOTS_DIR  = os.path.expanduser(
    '~/rnd_ws/plots_qta')
JSON_DIR   = os.path.expanduser(
    '~/rnd_ws/qta_results')

# Sensors to analyse with QTA
SENSORS_TO_ANALYSE = [
    'lidar_left',
    'lidar_right',
    'lidar_front',
    'lidar_front_right',
    'imu_angular_z',
    'imu_accel_x',
    'imu_accel_y',
    'odom_linear_x',
    'odom_angular_z',
]

# QTA thresholds
SLOPE_THRESHOLD    = 0.005  # minimum slope to be increasing/decreasing
CONSTANT_THRESHOLD = 0.05   # max variation to be constant
ZERO_THRESHOLD     = 0.02   # max mean to be zero

# Colors for QTA shapes (same style as Trushar!)
QTA_COLORS = {
    'is_constant':    'tab:blue',
    'is_increasing':  'tab:green',
    'is_decreasing':  'tab:red',
    'is_oscillating': 'tab:orange',
    'is_zero':        'tab:gray',
}

# Colors for action window backgrounds
ACTION_COLORS = {
    'idle':                '#E0E0E0',
    'searching_wall':      '#FFFF99',
    'approaching_wall':    '#FFD580',
    'wall_following':      '#90EE90',
    'obstacle_detected':   '#FFB347',
    'obstacle_avoidance':  '#87CEEB',
    'wall_reacquired':     '#DDA0DD',
    'wall_following_fail': '#FFB6C1',
}
# ──────────────────────────────────────────────────────────────


def apply_qta(values):
    """
    Applies QTA to a window of sensor values.
    Returns qualitative shape label.

    QTA Steps:
    1. Check if zero
    2. Check if constant (low variation)
    3. Fit straight line → get slope
    4. Classify slope direction
    """
    values = np.array(values, dtype=float)

    # Remove NaN and zero initialization values
    valid = values[~np.isnan(values)]

    if len(valid) < 3:
        return 'is_zero'

    mean_val = np.mean(valid)
    std_val  = np.std(valid)

    # Step 1: Check if zero
    if abs(mean_val) < ZERO_THRESHOLD:
        return 'is_zero'

    # Step 2: Check if constant
    cv = std_val / abs(mean_val) \
        if abs(mean_val) > 0 else std_val
    if cv < CONSTANT_THRESHOLD:
        return 'is_constant'

    # Step 3: Fit straight line
    x     = np.arange(len(valid))
    slope = np.polyfit(x, valid, 1)[0]

    # Normalize slope
    normalized_slope = slope / abs(mean_val) \
        if abs(mean_val) > 0 else slope

    # Step 4: Classify
    if cv > 0.15 and \
       abs(normalized_slope) < 0.01:
        return 'is_oscillating'

    if normalized_slope > SLOPE_THRESHOLD:
        return 'is_increasing'
    elif normalized_slope < -SLOPE_THRESHOLD:
        return 'is_decreasing'
    else:
        return 'is_constant'


def get_fitted_line(values, indices):
    """
    Fits a straight line through values.
    Returns fitted y values for plotting.
    (Same as Trushar's PLA approach!)
    """
    valid_values = np.array(values, dtype=float)
    x = np.array(indices, dtype=float)

    if len(valid_values) < 2:
        return valid_values

    slope, intercept = np.polyfit(
        x, valid_values, 1)
    fitted = slope * x + intercept

    return fitted


def analyse_csv_file(filepath):
    """
    Reads one cleaned CSV file and applies QTA
    to each action window for each sensor.

    Returns dictionary of QTA results.
    """
    df = pd.read_csv(filepath)

    # Convert timestamp to seconds
    df['timestamp'] = pd.to_datetime(
        df['timestamp'])
    t0 = df['timestamp'].iloc[0]
    df['time_sec'] = (
        df['timestamp'] - t0
    ).dt.total_seconds()

    # Get metadata
    run_id       = df['run_id'].iloc[0] \
        if 'run_id' in df.columns else 'unknown'
    scenario     = df['scenario'].iloc[0] \
        if 'scenario' in df.columns else 'unknown'
    example_type = df['example_type'].iloc[0] \
        if 'example_type' in df.columns else 'unknown'

    # Get unique action windows in order
    action_labels = df['action_label'].unique()

    # QTA results dictionary
    qta_results = {
        'run_id':       run_id,
        'scenario':     scenario,
        'example_type': example_type,
        'file':         os.path.basename(filepath),
        'windows':      {}
    }

    # Process each action window
    for label in df['action_label'].unique():
        window_df = df[
            df['action_label'] == label]

        if len(window_df) < 3:
            continue

        qta_results['windows'][label] = {}

        # Apply QTA to each sensor in this window
        for sensor in SENSORS_TO_ANALYSE:
            if sensor not in window_df.columns:
                continue

            values = window_df[sensor].values
            shape  = apply_qta(values)

            qta_results['windows'][label][sensor] = {
                'shape':      shape,
                'mean':       round(
                    float(np.mean(values)), 4),
                'std':        round(
                    float(np.std(values)), 4),
                'n_rows':     len(values)
            }

    return df, qta_results


def plot_qta_visualization(
        df, qta_results, sensor,
        output_path):
    """
    Creates QTA visualization for ONE sensor.
    Similar to Trushar's PLA graph!

    Shows:
    - Raw signal in gray
    - QTA fitted line per action window (colored)
    - Action window backgrounds
    """
    if sensor not in df.columns:
        return

    run_id   = qta_results['run_id']
    scenario = qta_results['scenario']

    fig, ax = plt.subplots(
        figsize=(14, 7))

    time_values   = df['time_sec'].values
    sensor_values = df[sensor].values

    # Plot raw signal in gray (like Trushar!)
    ax.plot(
        time_values,
        sensor_values,
        color='0.75',
        linewidth=1.2,
        label='Raw signal',
        zorder=1)

    # Track which QTA labels we've added to legend
    labels_added = set()

    # Process each action window
    prev_label = None
    start_idx  = 0

    # Get action boundaries
    boundaries = []
    labels_list = df['action_label'].values

    for i in range(1, len(labels_list)):
        if labels_list[i] != labels_list[i-1]:
            boundaries.append((
                start_idx, i,
                labels_list[start_idx]))
            start_idx = i
    boundaries.append((
        start_idx, len(labels_list),
        labels_list[start_idx]))

    # Plot each window
    for start_idx, end_idx, action_label \
            in boundaries:

        window_time   = time_values[
            start_idx:end_idx]
        window_values = sensor_values[
            start_idx:end_idx]

        if len(window_time) < 2:
            continue

        # Add background color for action window
        bg_color = ACTION_COLORS.get(
            action_label, 'white')
        ax.axvspan(
            window_time[0],
            window_time[-1],
            alpha=0.15,
            color=bg_color,
            zorder=0)

        # Get QTA shape for this window
        qta_shape = 'is_constant'
        if action_label in \
                qta_results['windows']:
            if sensor in \
                    qta_results['windows'][
                        action_label]:
                qta_shape = qta_results[
                    'windows'][action_label][
                    sensor]['shape']

        # Fit straight line (like Trushar's PLA!)
        indices = np.arange(
            start_idx, end_idx)
        fitted  = get_fitted_line(
            window_values, indices)

        # Plot fitted line with QTA color
        color = QTA_COLORS.get(
            qta_shape, 'black')

        legend_label = qta_shape \
            if qta_shape not in labels_added \
            else None

        ax.plot(
            window_time,
            fitted,
            color=color,
            linewidth=2.5,
            label=legend_label,
            zorder=2)

        labels_added.add(qta_shape)

        # Add action label text on graph
        mid_time = (window_time[0] +
                    window_time[-1]) / 2
        ax.text(
            mid_time,
            ax.get_ylim()[0] if
            ax.get_ylim()[0] != 0 else
            min(sensor_values) * 0.95,
            action_label.replace('_', '\n'),
            fontsize=6,
            ha='center',
            va='bottom',
            rotation=0,
            alpha=0.7)

    # Formatting
    ax.set_title(
        f'{sensor} — QTA Analysis\n'
        f'Run: {run_id} | '
        f'Scenario: {scenario}',
        fontsize=13,
        fontweight='bold')
    ax.set_xlabel(
        'Time since run start [s]',
        fontsize=11)
    ax.set_ylabel(
        sensor.replace('_', ' ').title(),
        fontsize=11)
    ax.grid(
        True,
        linestyle='--',
        alpha=0.4)
    ax.axhline(
        y=0,
        color='black',
        linewidth=0.8,
        alpha=0.6)

    # Add target line for lidar_left
    if sensor == 'lidar_left':
        ax.axhline(
            y=0.5,
            color='red',
            linestyle='--',
            linewidth=1.5,
            label='Target 0.5m',
            alpha=0.8)

    ax.legend(loc='best', fontsize=9)
    plt.tight_layout()

    plt.savefig(
        output_path,
        dpi=150,
        bbox_inches='tight')
    plt.close()

    print(f'  Saved: {os.path.basename(output_path)}')


def process_all_files():
    """
    Processes ALL cleaned CSV files.
    Creates QTA graphs and saves JSON results.
    """
    os.makedirs(PLOTS_DIR, exist_ok=True)
    os.makedirs(JSON_DIR, exist_ok=True)

    # Get all cleaned CSV files
    csv_files = sorted([
        f for f in os.listdir(INPUT_DIR)
        if f.endswith('.csv')
        and f != 'event_detection_summary.json'])

    if not csv_files:
        print(f'No CSV files found in {INPUT_DIR}')
        return

    print(f'Found {len(csv_files)} files to process')

    all_qta_results = []

    for filename in csv_files:
        filepath = os.path.join(
            INPUT_DIR, filename)

        print(f'\n{"="*50}')
        print(f'Processing: {filename}')

        try:
            df, qta_results = \
                analyse_csv_file(filepath)

            # Print QTA results
            print(f'  Run: {qta_results["run_id"]}')
            print(f'  Type: {qta_results["example_type"]}')
            print(f'  Windows found: '
                  f'{list(qta_results["windows"].keys())}')

            # Print QTA shapes for lidar_left
            print(f'\n  QTA shapes for lidar_left:')
            for window, sensors in \
                    qta_results['windows'].items():
                if 'lidar_left' in sensors:
                    shape = sensors[
                        'lidar_left']['shape']
                    print(f'    {window:25s} → {shape}')

            # Create plots folder for this run
            run_plot_dir = os.path.join(
                PLOTS_DIR,
                qta_results['run_id'])
            os.makedirs(
                run_plot_dir, exist_ok=True)

            # Create QTA graph for each sensor
            for sensor in SENSORS_TO_ANALYSE:
                if sensor not in df.columns:
                    continue

                plot_path = os.path.join(
                    run_plot_dir,
                    f'{sensor}_QTA.png')

                plot_qta_visualization(
                    df, qta_results,
                    sensor, plot_path)

            # Save QTA results as JSON
            json_path = os.path.join(
                JSON_DIR,
                f'{qta_results["run_id"]}_qta.json')

            with open(json_path, 'w') as f:
                json.dump(
                    qta_results, f, indent=2)

            all_qta_results.append(qta_results)

        except Exception as e:
            print(f'  ERROR: {e}')
            continue

    # Save combined results
    combined_path = os.path.join(
        JSON_DIR, 'all_qta_results.json')
    with open(combined_path, 'w') as f:
        json.dump(all_qta_results, f, indent=2)

    print(f'\n{"="*50}')
    print(f'COMPLETE!')
    print(f'Processed {len(all_qta_results)} files')
    print(f'Plots saved to: {PLOTS_DIR}')
    print(f'JSON saved to:  {JSON_DIR}')
    print('\nNext step: Run prolog_generator.py!')


# ── MAIN ──────────────────────────────────────────────────────
if __name__ == '__main__':
    process_all_files()