#!/usr/bin/env python3
"""
Event Detection Script for Robile Wall Following Data
=====================================================
This script:
1. Reads all CSV files (plain wall + pillar wall)
2. Finds event boundaries (where action label changes)
3. At each boundary checks which sensors change
4. Removes sensors that never change (useless!)
5. Saves new clean CSV files with only useful sensors

Author: Alisha Syed Karimulla
Project: Qualitative Analysis of Robotic Signal
         Components using ILP
"""

import pandas as pd
import numpy as np
import os
import json


# ── CONFIGURATION ─────────────────────────────────────────────

# Input data folders
PLAIN_WALL_DIR  = os.path.expanduser('~/rnd_ws/data')
PILLAR_WALL_DIR = os.path.expanduser('~/rnd_ws/data_pillar')

# Output folder for cleaned CSV files
OUTPUT_DIR = os.path.expanduser(
    '~/rnd_ws/data_cleaned')

# How many rows to look before and after each event
EVENT_WINDOW = 10

# Minimum change score to keep a sensor
# (0.0 = keep everything, 1.0 = very strict)
CHANGE_THRESHOLD = 0.05

# All sensor columns in CSV
ALL_SENSORS = [
    'lidar_right',
    'lidar_front_right',
    'lidar_front',
    'lidar_left',
    'odom_linear_x',
    'odom_angular_z',
    'pos_x',
    'pos_y',
    'cmd_linear_x',
    'cmd_angular_z',
    'imu_angular_z',
    'imu_accel_x',
    'imu_accel_y',
    'wheel_speed_0',
    'wheel_speed_1',
    'wheel_speed_2',
    'wheel_speed_3',
    'distance_travelled',
]
# ──────────────────────────────────────────────────────────────


def find_event_boundaries(df):
    """
    Finds all rows where action label CHANGES.
    These are the EVENT BOUNDARIES!

    Example:
    Row 50: approaching_wall → wall_following ← EVENT!
    Row 400: wall_following → obstacle_detected ← EVENT!
    """
    boundaries = []
    labels = df['action_label'].values

    for i in range(1, len(labels)):
        if labels[i] != labels[i-1]:
            boundaries.append({
                'row':        i,
                'from_label': labels[i-1],
                'to_label':   labels[i]
            })

    return boundaries


def calculate_sensor_change(df, boundary_row, sensor):
    """
    At one event boundary, calculates how much
    a sensor changes BEFORE vs AFTER the event.

    Returns a change score:
    - High score = sensor changes a lot at this event
    - Low score  = sensor barely changes
    """
    # Get rows before event
    start_before = max(0, boundary_row - EVENT_WINDOW)
    before_values = df[sensor].iloc[
        start_before:boundary_row].values

    # Get rows after event
    end_after = min(len(df),
                    boundary_row + EVENT_WINDOW)
    after_values = df[sensor].iloc[
        boundary_row:end_after].values

    # Remove zeros (uninitialized sensor values)
    before_values = before_values[before_values != 0.0]
    after_values  = after_values[after_values != 0.0]

    # Not enough data
    if len(before_values) < 3 or len(after_values) < 3:
        return 0.0

    mean_before = np.mean(before_values)
    mean_after  = np.mean(after_values)

    # If both are near zero → sensor is useless
    if abs(mean_before) < 0.01 and \
       abs(mean_after) < 0.01:
        return 0.0

    # Calculate relative change
    max_val = max(abs(mean_before),
                  abs(mean_after), 0.001)
    change_score = abs(mean_after - mean_before) / max_val

    return round(change_score, 4)


def detect_useful_sensors(df, filename):
    """
    For one CSV file:
    1. Finds all event boundaries
    2. At each boundary checks all sensors
    3. Returns list of sensors that change
       at at least one event

    This is the CORE of event detection!
    """
    print(f'\n  Finding events in: {filename}')

    # Find all event boundaries
    boundaries = find_event_boundaries(df)
    print(f'  Events found: {len(boundaries)}')

    for b in boundaries:
        print(f'    Row {b["row"]}: '
              f'{b["from_label"]} → {b["to_label"]}')

    # For each sensor calculate total change
    # across ALL events
    sensor_scores = {}

    for sensor in ALL_SENSORS:
        if sensor not in df.columns:
            continue

        # Sum of change scores across all events
        total_change = 0.0
        for boundary in boundaries:
            change = calculate_sensor_change(
                df, boundary['row'], sensor)
            total_change += change

        sensor_scores[sensor] = round(total_change, 4)

    # Sort sensors by change score
    sorted_sensors = sorted(
        sensor_scores.items(),
        key=lambda x: x[1],
        reverse=True)

    print(f'\n  Sensor change scores:')
    useful_sensors = []

    for sensor, score in sorted_sensors:
        if score > CHANGE_THRESHOLD:
            status = '✅ KEEP'
            useful_sensors.append(sensor)
        else:
            status = '❌ REMOVE'
        print(f'    {sensor:25s}: '
              f'{score:.4f} {status}')

    return useful_sensors


def process_csv_file(filepath, output_dir,
                     scenario, run_id):
    """
    Processes one CSV file:
    1. Detects useful sensors
    2. Creates new clean CSV with only useful sensors
    3. Saves to output folder
    """
    filename = os.path.basename(filepath)
    print(f'\n{"="*60}')
    print(f'Processing: {filename}')
    print(f'Scenario: {scenario} | Run: {run_id}')

    # Read CSV
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f'ERROR reading file: {e}')
        return None

    # Remove rows where all sensors are zero
    # (initialization rows)
    sensor_cols = [s for s in ALL_SENSORS
                   if s in df.columns]
    df = df[df[sensor_cols].any(axis=1)]
    df = df.reset_index(drop=True)

    print(f'Total rows: {len(df)}')
    print(f'Action labels: '
          f'{df["action_label"].unique().tolist()}')

    # Detect useful sensors
    useful_sensors = detect_useful_sensors(df, filename)

    if not useful_sensors:
        print('WARNING: No useful sensors found!')
        return None

    print(f'\n  Keeping {len(useful_sensors)} sensors:')
    print(f'  {useful_sensors}')

    # Create clean dataframe with useful sensors only
    cols_to_keep = (['timestamp'] +
                    useful_sensors +
                    ['action_label'])

    # Only keep columns that exist
    cols_to_keep = [c for c in cols_to_keep
                    if c in df.columns]

    clean_df = df[cols_to_keep].copy()

    # Add metadata columns
    clean_df.insert(1, 'scenario', scenario)
    clean_df.insert(2, 'run_id', run_id)

    # Add explicit good/bad label
    if 'good' in scenario:
        example_type = 'positive'
    else:
        example_type = 'negative'
    clean_df.insert(3, 'example_type', example_type)

    # Save clean CSV
    os.makedirs(output_dir, exist_ok=True)
    output_filename = f'{run_id}_{scenario}.csv'
    output_path = os.path.join(
        output_dir, output_filename)

    clean_df.to_csv(output_path, index=False)
    print(f'\n  ✅ Saved: {output_filename}')
    print(f'  Original columns: {len(df.columns)}')
    print(f'  Clean columns:    {len(clean_df.columns)}')

    return {
        'run_id':          run_id,
        'scenario':        scenario,
        'original_file':   filename,
        'useful_sensors':  useful_sensors,
        'total_rows':      len(clean_df),
        'action_labels':   df['action_label']
                           .unique().tolist()
    }


def process_all_files():
    """
    Processes ALL CSV files from both scenarios.
    """

    # ── DEFINE YOUR FILES ──────────────────────────
    # Plain wall good runs
    plain_good = [
        'wall_data_2026-07-04_13-52-05.csv',
        'wall_data_2026-07-04_14-02-30.csv',
        'wall_data_2026-07-04_14-04-55.csv',
        'wall_data_2026-07-04_14-06-45.csv',
        'wall_data_2026-07-04_14-08-22.csv',
        'wall_data_2026-07-04_14-10-18.csv',
        'wall_data_2026-07-04_14-11-55.csv',
        'wall_data_2026-07-04_14-13-37.csv',
        'wall_data_2026-07-04_14-15-50.csv',
        'wall_data_2026-07-04_14-28-30.csv',
    ]

    # Plain wall bad runs
    plain_bad = [
        'wall_data_2026-07-04_13-24-30.csv',
        'wall_data_2026-07-04_14-32-58.csv',
        'wall_data_2026-07-04_14-43-56.csv',
        'wall_data_2026-07-04_14-45-40.csv',
        'wall_data_2026-07-04_14-47-20.csv',
    ]

    # Pillar wall good runs
    pillar_good = [
        'pillar_data_2026-07-09_11-44-35.csv',
        'pillar_data_2026-07-09_11-53-16.csv',
        'pillar_data_2026-07-09_11-56-46.csv',
        'pillar_data_2026-07-09_11-58-40.csv',
        'pillar_data_2026-07-09_12-04-08.csv',
        'pillar_data_2026-07-09_12-07-16.csv',
        'pillar_data_2026-07-09_12-09-18.csv',
    ]

    # Pillar wall bad runs
    pillar_bad = [
        'pillar_data_2026-07-09_12-17-49.csv',
        'pillar_data_2026-07-09_12-28-34.csv',
        'pillar_data_2026-07-09_12-31-57.csv',
    ]
    # ──────────────────────────────────────────────

    all_results = []

    # Process plain wall good runs
    print('\n' + '='*60)
    print('PLAIN WALL — GOOD RUNS')
    print('='*60)
    for i, filename in enumerate(plain_good):
        filepath = os.path.join(
            PLAIN_WALL_DIR, filename)
        if os.path.exists(filepath):
            result = process_csv_file(
                filepath,
                OUTPUT_DIR,
                'plain_wall_good',
                f'pw_good_{i+1:02d}')
            if result:
                all_results.append(result)

    # Process plain wall bad runs
    print('\n' + '='*60)
    print('PLAIN WALL — BAD RUNS')
    print('='*60)
    for i, filename in enumerate(plain_bad):
        filepath = os.path.join(
            PLAIN_WALL_DIR, filename)
        if os.path.exists(filepath):
            result = process_csv_file(
                filepath,
                OUTPUT_DIR,
                'plain_wall_bad',
                f'pw_bad_{i+1:02d}')
            if result:
                all_results.append(result)

    # Process pillar wall good runs
    print('\n' + '='*60)
    print('PILLAR WALL — GOOD RUNS')
    print('='*60)
    for i, filename in enumerate(pillar_good):
        filepath = os.path.join(
            PILLAR_WALL_DIR, filename)
        if os.path.exists(filepath):
            result = process_csv_file(
                filepath,
                OUTPUT_DIR,
                'pillar_wall_good',
                f'pill_good_{i+1:02d}')
            if result:
                all_results.append(result)

    # Process pillar wall bad runs
    print('\n' + '='*60)
    print('PILLAR WALL — BAD RUNS')
    print('='*60)
    for i, filename in enumerate(pillar_bad):
        filepath = os.path.join(
            PILLAR_WALL_DIR, filename)
        if os.path.exists(filepath):
            result = process_csv_file(
                filepath,
                OUTPUT_DIR,
                'pillar_wall_bad',
                f'pill_bad_{i+1:02d}')
            if result:
                all_results.append(result)

    return all_results


def save_summary(results):
    """
    Saves a summary of all processed files
    showing which sensors were kept/removed.
    """
    summary_path = os.path.join(
        OUTPUT_DIR, 'event_detection_summary.json')

    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f'\n✅ Summary saved: {summary_path}')

    # Print overall sensor frequency
    print('\n' + '='*60)
    print('SENSOR FREQUENCY ACROSS ALL RUNS')
    print('(how often each sensor was kept)')
    print('='*60)

    sensor_count = {}
    for result in results:
        for sensor in result['useful_sensors']:
            sensor_count[sensor] = \
                sensor_count.get(sensor, 0) + 1

    total_runs = len(results)
    sorted_sensors = sorted(
        sensor_count.items(),
        key=lambda x: x[1],
        reverse=True)

    for sensor, count in sorted_sensors:
        percentage = (count / total_runs) * 100
        bar = '█' * int(percentage / 5)
        print(f'{sensor:25s}: '
              f'{count:2d}/{total_runs} '
              f'({percentage:5.1f}%) {bar}')


# ── MAIN ───────────────────────────────────────────────────────
if __name__ == '__main__':

    print('='*60)
    print('EVENT DETECTION SCRIPT')
    print('Robile Wall Following Dataset')
    print('='*60)

    # Process all files
    results = process_all_files()

    # Save summary
    save_summary(results)

    print('\n' + '='*60)
    print('COMPLETE!')
    print(f'Processed {len(results)} CSV files')
    print(f'Clean files saved to: {OUTPUT_DIR}')
    print('\nNext step: Run QTA on clean files!')
    print('='*60)