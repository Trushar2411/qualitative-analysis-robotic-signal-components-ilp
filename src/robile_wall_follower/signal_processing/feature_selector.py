#!/usr/bin/env python3
"""
Feature Selector
=================
Selects stable sensors for ILP learning!

Uses Mean Absolute Difference (MAD)
to measure sensor noise level:

MAD = mean(|value[i+1] - value[i]|)

High MAD = noisy sensor → remove!
Low MAD  = stable sensor → keep!

This is necessary for mobile robots
because some sensors (IMU, lidar_front)
show high frequency noise at row level
making them unsuitable for row-by-row
delta classification!

Input:  data_cleaned/
Output: data_cleaned_selected/
        selected_sensors.txt

Author: Alisha Syed Karimulla
Project: Qualitative Analysis of Robotic
         Signal Components using ILP
"""

import os
import pandas as pd
import numpy as np


# ── CONFIGURATION ─────────────────────────────────────────────
INPUT_DIR  = os.path.expanduser(
    '~/rnd_ws/data_cleaned')
OUTPUT_DIR = os.path.expanduser(
    '~/rnd_ws/data_cleaned_selected')

# Sensors to evaluate
ALL_SENSORS = [
    'lidar_left',
    'lidar_right',
    'lidar_front',
    'lidar_front_right',
    'imu_accel_x',
    'imu_accel_y',
    'imu_angular_z',
    'odom_linear_x',
]

# MAD threshold for feature selection!
# Sensors with MAD > threshold → removed!
# Sensors with MAD < threshold → kept!
MAD_THRESHOLD = 0.15
# ──────────────────────────────────────────────────────────────


def calculate_mad(combined_df, sensor):
    """
    Calculates Mean Absolute Difference
    for one sensor across all runs!

    MAD = mean(|value[i+1] - value[i]|)

    This measures how much sensor
    changes between consecutive rows!

    High MAD = noisy = bad for ILP!
    Low MAD  = stable = good for ILP!
    """
    if sensor not in combined_df.columns:
        return None

    values = combined_df[sensor].values
    deltas = []

    for i in range(len(values) - 1):
        v1 = values[i]
        v2 = values[i+1]

        if pd.isna(v1) or pd.isna(v2):
            continue

        deltas.append(
            abs(float(v2) - float(v1)))

    if not deltas:
        return None

    return np.mean(deltas)


def select_features(combined_df):
    """
    Selects stable sensors using MAD!

    Returns list of selected sensors
    and their MAD values!
    """
    print('Calculating MAD per sensor:')
    print()

    selected = []
    removed  = []
    mad_values = {}

    for sensor in ALL_SENSORS:
        mad = calculate_mad(
            combined_df, sensor)

        if mad is None:
            print(f'  {sensor:20s} → NOT FOUND')
            continue

        mad_values[sensor] = mad

        if mad < MAD_THRESHOLD:
            selected.append(sensor)
            status = '✅ SELECTED'
        else:
            removed.append(sensor)
            status = '❌ REMOVED (noisy!)'

        print(f'  {sensor:20s} '
              f'MAD={mad:.4f} '
              f'→ {status}')

    print()
    print(f'Selected {len(selected)} sensors:')
    for s in selected:
        print(f'  → {s} (MAD={mad_values[s]:.4f})')

    print()
    print(f'Removed {len(removed)} sensors:')
    for s in removed:
        print(f'  → {s} (MAD={mad_values[s]:.4f})')

    return selected, mad_values


def save_selected_csvs(selected_sensors):
    """
    Saves CSV files with only
    selected sensors!
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    csv_files = sorted([
        f for f in os.listdir(INPUT_DIR)
        if f.endswith('.csv')])

    print(f'\nSaving {len(csv_files)} files...')

    for filename in csv_files:
        filepath = os.path.join(
            INPUT_DIR, filename)

        try:
            df = pd.read_csv(filepath)

            # Keep selected sensors
            # plus action_label and timestamp!
            cols_to_keep = []

            # Keep timestamp if exists!
            for col in ['timestamp',
                        'time', 'bag_time']:
                if col in df.columns:
                    cols_to_keep.append(col)
                    break

            # Keep selected sensors!
            for sensor in selected_sensors:
                if sensor in df.columns:
                    cols_to_keep.append(sensor)

            # Always keep action_label!
            if 'action_label' in df.columns:
                cols_to_keep.append(
                    'action_label')

            df_selected = df[cols_to_keep]

            output_path = os.path.join(
                OUTPUT_DIR, filename)
            df_selected.to_csv(
                output_path, index=False)

        except Exception as e:
            print(f'  ERROR: {filename}: {e}')

    print(f'Saved to: {OUTPUT_DIR}')


def save_sensor_report(
        selected_sensors, mad_values):
    """Saves feature selection report."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    report_path = os.path.join(
        OUTPUT_DIR, 'selected_sensors.txt')

    with open(report_path, 'w') as f:
        f.write('FEATURE SELECTION REPORT\n')
        f.write('='*60 + '\n\n')
        f.write('Method: Mean Absolute Difference\n')
        f.write(
            f'Threshold: {MAD_THRESHOLD}\n\n')
        f.write(
            'MAD = mean(|value[i+1] - value[i]|)\n')
        f.write(
            'Sensors with MAD > threshold\n'
            'are removed as too noisy!\n\n')

        f.write('ALL SENSORS:\n')
        for sensor in ALL_SENSORS:
            if sensor not in mad_values:
                continue
            mad = mad_values[sensor]
            status = 'SELECTED' \
                if sensor in selected_sensors \
                else 'REMOVED'
            f.write(
                f'  {sensor:20s} '
                f'MAD={mad:.4f} '
                f'→ {status}\n')

        f.write('\n')
        f.write('SELECTED SENSORS:\n')
        for sensor in selected_sensors:
            f.write(f'  {sensor}\n')

    print(f'\nReport: {report_path}')


# ── MAIN ──────────────────────────────────────────────────────
if __name__ == '__main__':

    print('='*60)
    print('FEATURE SELECTOR')
    print('Selecting stable sensors for ILP!')
    print(f'MAD threshold: {MAD_THRESHOLD}')
    print('='*60)
    print()

    # Load all CSV files!
    csv_files = sorted([
        f for f in os.listdir(INPUT_DIR)
        if f.endswith('.csv')])

    print(f'Loading {len(csv_files)} CSV files...')

    all_dfs = []
    for filename in csv_files:
        try:
            df = pd.read_csv(
                os.path.join(
                    INPUT_DIR, filename))
            all_dfs.append(df)
        except Exception as e:
            print(f'  ERROR: {filename}: {e}')

    combined = pd.concat(
        all_dfs, ignore_index=True)
    print(f'Total rows: {len(combined)}')
    print()

    # Select stable sensors!
    selected_sensors, mad_values = \
        select_features(combined)

    # Save selected CSVs!
    save_selected_csvs(selected_sensors)

    # Save report!
    save_sensor_report(
        selected_sensors, mad_values)

    print()
    print('='*60)
    print('COMPLETE!')
    print(f'Selected sensors: {selected_sensors}')
    print('='*60)