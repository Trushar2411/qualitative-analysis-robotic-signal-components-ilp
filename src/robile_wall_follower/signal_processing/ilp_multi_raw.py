#!/usr/bin/env python3
"""
ILP Multi-Sensor Phase Learner - RAW
======================================
Same approach as Trushar!

Combines ALL CSV files!
For EACH phase:
- Creates facts for ALL sensors!
- Row by row delta classification
- pos = rows IN this phase
- neg = rows NOT in this phase
- Popper finds COMBINATION of sensors!

Author: Alisha Syed Karimulla
Project: Qualitative Analysis of Robotic
         Signal Components using ILP
"""

import os
import subprocess
import pandas as pd
import numpy as np


# ── CONFIGURATION ─────────────────────────────────────────────
# DATA_DIR    = os.path.expanduser(
#     '~/rnd_ws/data_cleaned')
# # DATA_DIR    = os.path.expanduser(
# #     '~/rnd_ws/data_cleaned_selected')
# POPPER_DIR  = os.path.expanduser(
#     '~/rnd_ws/popper_run')
# RESULTS_DIR = os.path.expanduser(
#     '~/rnd_ws/ilp_results_multi_raw')
# POPPER_PATH = os.path.expanduser(
#     '~/Popper/popper.py')
# PYTHON_PATH = os.path.expanduser(
#     '~/popper_env/bin/python')
# ── CONFIGURATION ─────────────────────────────────────────────
DATA_DIR    = os.path.expanduser(
    '~/rnd_ws/data_cleaned')
POPPER_DIR  = os.path.expanduser(
    '~/rnd_ws/popper_run')
POPPER_PATH = os.path.expanduser(
    '~/Popper/popper.py')
PYTHON_PATH = os.path.expanduser(
    '~/popper_env/bin/python')

# ── CHANGE THESE FOR EACH TASK ────────────────────────────────
TASK        = 'pw'
RESULTS_DIR = os.path.expanduser(
    '~/rnd_ws/ilp_results_multi_raw_plain')
# ──────────────────────────────────────────────────────────────

PHASES = [
    'approaching_wall',
    'wall_following',
    'obstacle_detected',
    'obstacle_avoidance',
    'wall_reacquired',
    'wall_following_fail',
    'searching_wall',
]

# ALL sensors used together!
# Same as Trushar uses all 18 signals!
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
# ALL_SENSORS = [
#     'lidar_left',
#     'lidar_right',
#     'imu_accel_x',
#     'imu_angular_z',
#     'odom_linear_x',
# ]
# ALL_SENSORS = [
#     'lidar_left',
#     'lidar_right',
#     'pos_x',
#     'pos_y',
#     'odom_linear_x',
# ]

# Thresholds per sensor type
THRESHOLDS = {
    'lidar_left':        0.01,
    'lidar_right':       0.01,
    'lidar_front':       0.01,
    'lidar_front_right': 0.01,
    'imu_accel_x':       0.01,
    'imu_accel_y':       0.01,
    'imu_angular_z':     0.01,
    'odom_linear_x':     0.001,
}
# ──────────────────────────────────────────────────────────────


# def load_and_combine_csv():
#     """
#     Loads ALL CSV files and combines
#     into one big dataframe!
#     Same as Trushar's approach!
#     """
#     all_dfs   = []
#     csv_files = sorted([
#         f for f in os.listdir(DATA_DIR)
#         if f.endswith('.csv')])

#     print(f'Found {len(csv_files)} CSV files')

#     for filename in csv_files:
#         try:
#             df = pd.read_csv(
#                 os.path.join(
#                     DATA_DIR, filename))
#             all_dfs.append(df)
#         except Exception as e:
#             print(f'  ERROR: {filename}: {e}')

#     # combined = pd.concat(
#     #     all_dfs, ignore_index=True)
#     # print(f'Total rows: {len(combined)}')
#     # return combined
#     combined = pd.concat(
#         all_dfs, ignore_index=True)
#     print(f'Total rows before: {len(combined)}')

#     # Downsample every 10th row!
#     # Reduces noise like Trushar's small dataset!
#     # combined = combined.iloc[::10].reset_index(
#     #     drop=True)
#     # print(f'Total rows after downsampling: '
#     #       f'{len(combined)}')
#     return combined


# def load_and_combine_csv():
#     """
#     Loads ALL CSV files and combines
#     into one big dataframe!
#     Then balances classes!
#     """
#     all_dfs   = []
#     csv_files = sorted([
#         f for f in os.listdir(DATA_DIR)
#         if f.endswith('.csv')])

#     print(f'Found {len(csv_files)} CSV files')

#     for filename in csv_files:
#         try:
#             df = pd.read_csv(
#                 os.path.join(
#                     DATA_DIR, filename))
#             all_dfs.append(df)
#         except Exception as e:
#             print(f'  ERROR: {filename}: {e}')

#     combined = pd.concat(
#         all_dfs, ignore_index=True)
#     print(f'Total rows before: {len(combined)}')

#     # Balance classes!
#     # Limit each phase to MAX_ROWS!
#     # Prevents dominant wall_following
#     # from overwhelming learner!
#     MAX_ROWS = 10

#     balanced_dfs = []
#     for phase in combined['action_label'].unique():
#         phase_df = combined[
#             combined['action_label'] == phase]
#         if len(phase_df) > MAX_ROWS:
#             phase_df = phase_df.sample(
#                 n=MAX_ROWS,
#                 random_state=42)
#         balanced_dfs.append(phase_df)

#     combined = pd.concat(
#         balanced_dfs,
#         ignore_index=True)

#     print(f'After balancing:')
#     print(combined['action_label'].value_counts())
#     print(f'Total rows: {len(combined)}')

#     return combined


def load_and_combine_csv():
    """
    Loads GOOD run CSV files only!
    Filtered by task!
    Combines into one dataframe!
    """
    all_dfs   = []
    csv_files = sorted([
        f for f in os.listdir(DATA_DIR)
        if f.endswith('.csv')])

    print(f'Loading good run CSV files '
          f'for task={TASK}...')

    for filename in csv_files:
        # Good runs only!
        if 'good' not in filename:
            continue
        # Filter by task!
        if TASK == 'pw' and \
                'pw' not in filename:
            continue
        if TASK == 'pill' and \
                'pill' not in filename:
            continue
        # TASK == 'all' loads all good runs!

        try:
            df = pd.read_csv(
                os.path.join(
                    DATA_DIR, filename))
            all_dfs.append(df)
            print(f'  Loaded: {filename}')
        except Exception as e:
            print(f'  ERROR: {filename}: {e}')

    combined = pd.concat(
        all_dfs, ignore_index=True)
    print(f'Total rows: {len(combined)}')
    return combined

def generate_pred_name(sensor, label):
    """Creates predicate name."""
    sensor_short = {
        'lidar_left':        'lidar',
        'lidar_right':       'lidar_r',
        'lidar_front':       'lidar_f',
        'lidar_front_right': 'lidar_fr',
        'imu_accel_x':       'imu_x',
        'imu_accel_y':       'imu_y',
        'imu_angular_z':     'imu',
        'odom_linear_x':     'odom',
    }.get(sensor, sensor[:5])

    return f'{sensor_short}_{label}'


def generate_bias(predicates):
    """Generates bias file."""
    lines = []
    lines.append('head_pred(phase_correct,1).')
    for pred in sorted(predicates):
        lines.append(f'body_pred({pred},1).')
    lines.append('type(phase_correct,(state,)).')
    for pred in sorted(predicates):
        lines.append(f'type({pred},(state,)).')
    lines.append(
        'direction(phase_correct,(in,)).')
    for pred in sorted(predicates):
        lines.append(
            f'direction({pred},(in,)).')
    # Allow up to 4 body predicates!
    # Same as Trushar!
    lines.append('max_clauses(3).')
    lines.append('max_body(4).')
    lines.append('max_vars(1).')
    return '\n'.join(lines)


def run_popper(timeout=120):
    """Runs Popper ILP."""
    cmd = [
        PYTHON_PATH,
        POPPER_PATH,
        POPPER_DIR,
        '--stats',
        '--timeout', str(timeout)
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True)
    return result.stdout + result.stderr


def extract_solution(popper_output):
    """Extracts learned rules."""
    lines  = popper_output.split('\n')
    rules  = []
    scores = {}

    in_solution = False
    for line in lines:
        if '** SOLUTION **' in line:
            in_solution = True
            continue
        if in_solution and '****' in line:
            in_solution = False
            continue
        if in_solution and line.strip():
            if 'Precision' in line:
                parts = line.split()
                for p in parts:
                    if 'Precision:' in p:
                        scores['precision'] = float(
                            p.split(':')[1])
                    if 'Recall:' in p:
                        scores['recall'] = float(
                            p.split(':')[1])
                    if 'TP:' in p:
                        scores['tp'] = int(
                            p.split(':')[1])
                    if 'FN:' in p:
                        scores['fn'] = int(
                            p.split(':')[1])
                    if 'TN:' in p:
                        scores['tn'] = int(
                            p.split(':')[1])
                    if 'FP:' in p:
                        scores['fp'] = int(
                            p.split(':')[1])
            elif 'phase_correct' in line:
                rules.append(line.strip())

    if 'NO SOLUTION' in popper_output:
        return None, {}

    return rules, scores


def generate_facts_for_phase(
        df, target_phase):
    """
    Generates Prolog facts for ALL sensors!
    Same as Trushar!

    For each row pair in same phase:
    → Calculate delta for ALL sensors
    → Create facts for ALL sensors
    → pos = IN target phase
    → neg = NOT in target phase
    """
    facts        = []
    pos_examples = []
    neg_examples = []
    predicates   = set()

    state_counter = 0

    for i in range(len(df) - 1):

        curr_phase = str(
            df.iloc[i]['action_label'])
        next_phase = str(
            df.iloc[i+1]['action_label'])

        # Never cross phase boundary!
        if curr_phase != next_phase:
            continue

        state_id = f's{state_counter}'
        state_counter += 1

        # Create facts for ALL sensors!
        for sensor in ALL_SENSORS:
            if sensor not in df.columns:
                continue

            v1 = df.iloc[i][sensor]
            v2 = df.iloc[i+1][sensor]

            if pd.isna(v1) or pd.isna(v2):
                continue

            delta = float(v2) - float(v1)
            threshold = THRESHOLDS.get(
                sensor, 0.01)

            if delta > threshold:
                label = 'increases'
            elif delta < -threshold:
                label = 'decreases'
            else:
                label = 'constant'

            pred = generate_pred_name(
                sensor, label)
            predicates.add(pred)
            facts.append(
                f'{pred}({state_id}).')

        # pos = IN target phase!
        # neg = NOT in target phase!
        if curr_phase == target_phase:
            pos_examples.append(
                f'pos(phase_correct'
                f'({state_id})).')
        else:
            neg_examples.append(
                f'neg(phase_correct'
                f'({state_id})).')

    return (facts, pos_examples,
            neg_examples, predicates)


def save_results(
        phase, rules, scores,
        popper_output):
    """Saves results."""
    os.makedirs(RESULTS_DIR, exist_ok=True)

    filename = os.path.join(
        RESULTS_DIR,
        f'{phase}_rules.txt')

    with open(filename, 'w') as f:
        f.write(f'Phase: {phase}\n')
        f.write('Method: RAW MULTI-SENSOR\n')
        f.write('All sensors combined!\n')
        f.write('Same as Trushar!\n')
        f.write('='*50 + '\n\n')

        if rules:
            f.write('LEARNED RULES:\n')
            for rule in rules:
                f.write(f'  {rule}\n')
            f.write('\n')
            f.write('SCORES:\n')
            for k, v in scores.items():
                f.write(f'  {k}: {v}\n')
        else:
            f.write('NO SOLUTION FOUND\n')

        f.write('\n\nFULL POPPER OUTPUT:\n')
        f.write(popper_output)


def generate_summary(all_results):
    """Generates summary."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(
        RESULTS_DIR, 'summary_raw.txt')

    with open(path, 'w') as f:
        f.write('ILP MULTI-SENSOR SUMMARY\n')
        f.write('Method: RAW MULTI-SENSOR\n')
        f.write('(No QTA!)\n')
        f.write('='*60 + '\n\n')
        f.write('Same as Trushar!\n')
        f.write('All sensors combined!\n')
        f.write('pos = rows IN phase\n')
        f.write('neg = rows NOT in phase\n\n')

        for phase, rules, scores \
                in all_results:
            f.write(f'Phase: {phase}\n')

            if rules:
                f.write('Rules:\n')
                for rule in rules:
                    f.write(f'  {rule}\n')
                f.write(
                    f'Precision: '
                    f'{scores.get("precision","N/A")}\n')
                f.write(
                    f'Recall: '
                    f'{scores.get("recall","N/A")}\n')
            else:
                f.write('NO SOLUTION\n')
            f.write('\n')

    print(f'\nSummary: {path}')
    return path


# ── MAIN ──────────────────────────────────────────────────────
if __name__ == '__main__':

    print('='*60)
    print('ILP MULTI-SENSOR - RAW')
    print('Same as Trushar!')
    print('ALL sensors combined!')
    print('pos = rows IN phase')
    print('neg = rows NOT in phase')
    print('='*60)

    # Load and combine ALL CSV files!
    df = load_and_combine_csv()

    all_phase_results = []

    for phase in PHASES:
        print(f'\n\n{"#"*60}')
        print(f'# PHASE: {phase}')
        print(f'{"#"*60}')

        (facts, pos_examples,
         neg_examples,
         predicates) = \
            generate_facts_for_phase(
                df, phase)

        print(f'Total states: {len(facts)//len(ALL_SENSORS)}')
        print(f'pos={len(pos_examples)} '
              f'neg={len(neg_examples)}')

        if not pos_examples or \
           not neg_examples:
            print('Not enough examples!')
            all_phase_results.append((
                phase, None, {}))
            continue

        os.makedirs(POPPER_DIR, exist_ok=True)

        with open(os.path.join(
                POPPER_DIR, 'bk.pl'), 'w') as f:
            f.write('\n'.join(facts))

        exs = (
            '% Positive examples\n' +
            '\n'.join(pos_examples) +
            '\n\n% Negative examples\n' +
            '\n'.join(neg_examples))

        with open(os.path.join(
                POPPER_DIR, 'exs.pl'), 'w') as f:
            f.write(exs)

        with open(os.path.join(
                POPPER_DIR, 'bias.pl'), 'w') as f:
            f.write(generate_bias(predicates))

        print('Running Popper...')
        popper_output = run_popper()
        rules, scores = extract_solution(
            popper_output)

        if rules:
            print(f'✅ SOLUTION FOUND!')
            for r in rules:
                print(f'  {r}')
            print(f'Scores: {scores}')
        else:
            print(f'❌ NO SOLUTION')

        save_results(
            phase, rules, scores,
            popper_output)

        all_phase_results.append((
            phase, rules, scores))

    generate_summary(all_phase_results)

    print('\n' + '='*60)
    print('COMPLETE!')
    print(f'Results: {RESULTS_DIR}')
    print('='*60)