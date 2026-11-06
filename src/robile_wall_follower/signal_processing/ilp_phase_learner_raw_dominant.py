#!/usr/bin/env python3
"""
ILP Phase Learner WITHOUT QTA
==============================
Uses row-by-row delta comparison
then picks DOMINANT label per run!

For each run in each phase:
1. Count increases/decreases/constant
   across all consecutive row pairs
2. Pick dominant label for that run
3. Create ONE Prolog fact per run!

This is the RAW baseline approach!
Used for comparison with QTA!

Author: Alisha Syed Karimulla
Project: Qualitative Analysis of Robotic
         Signal Components using ILP
"""

import os
import subprocess
import pandas as pd
import numpy as np


# ── CONFIGURATION ─────────────────────────────────────────────
DATA_DIR    = os.path.expanduser(
    '~/rnd_ws/data_cleaned')
POPPER_DIR  = os.path.expanduser(
    '~/rnd_ws/popper_run')
RESULTS_DIR = os.path.expanduser(
    '~/rnd_ws/ilp_results_raw')
POPPER_PATH = os.path.expanduser(
    '~/Popper/popper.py')
PYTHON_PATH = os.path.expanduser(
    '~/popper_env/bin/python')

# Try ALL sensors!
SENSORS_TO_TRY = [
    'lidar_left',
    'lidar_right',
    'lidar_front',
    'lidar_front_right',
    'imu_accel_x',
    'imu_accel_y',
    'imu_angular_z',
    'odom_linear_x',
]

PHASES = [
    'approaching_wall',
    'wall_following',
    'obstacle_detected',
    'obstacle_avoidance',
    'wall_reacquired',
    'wall_following_fail',
    'searching_wall',
]

# Fixed threshold for delta
DELTA_THRESHOLD = 0.01
# ──────────────────────────────────────────────────────────────


def load_all_csv_files():
    """Loads all cleaned CSV files."""
    all_runs  = []
    csv_files = sorted([
        f for f in os.listdir(DATA_DIR)
        if f.endswith('.csv')])

    print(f'Found {len(csv_files)} CSV files')

    for filename in csv_files:
        filepath = os.path.join(
            DATA_DIR, filename)
        try:
            df = pd.read_csv(filepath)
            if 'good' in filename:
                example_type = 'positive'
            else:
                example_type = 'negative'
            parts  = filename.replace(
                '.csv', '').split('_')
            run_id = '_'.join(parts[:3])
            all_runs.append({
                'run_id':       run_id,
                'example_type': example_type,
                'filename':     filename,
                'df':           df
            })
        except Exception as e:
            print(f'  ERROR: {filename}: {e}')

    print(f'Loaded {len(all_runs)} runs')
    return all_runs


def generate_predicate_name(
        phase, sensor, label):
    """Creates predicate name."""
    phase_short = {
        'approaching_wall':    'approach',
        'wall_following':      'wf',
        'wall_following_fail': 'fail',
        'obstacle_detected':   'detect',
        'obstacle_avoidance':  'avoid',
        'wall_reacquired':     'reacquire',
        'searching_wall':      'search',
    }.get(phase, phase[:6])

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

    return (f'{phase_short}_'
            f'{sensor_short}_'
            f'{label}')


def process_all_runs(all_runs, phase, sensor):
    """
    For each run:
    1. Count increases/decreases/constant
       across ALL row pairs in phase window
    2. Pick DOMINANT label for that run
    3. Create ONE fact per run!

    Key difference from QTA:
    QTA uses normalized slope
    RAW uses dominant delta count!
    """
    results    = []
    predicates = set()

    for run in all_runs:
        run_id       = run['run_id']
        example_type = run['example_type']
        df           = run['df']

        if 'action_label' not in df.columns:
            continue

        phase_df = df[
            df['action_label'] == phase
        ].reset_index(drop=True)

        if len(phase_df) < 2:
            continue

        if sensor not in phase_df.columns:
            continue

        values = phase_df[sensor].values

        # Count labels across all row pairs
        inc = dec = con = 0
        for i in range(len(values) - 1):
            v1 = values[i]
            v2 = values[i + 1]
            if np.isnan(v1) or np.isnan(v2):
                continue
            delta = v2 - v1
            if delta > DELTA_THRESHOLD:
                inc += 1
            elif delta < -DELTA_THRESHOLD:
                dec += 1
            else:
                con += 1

        total = inc + dec + con
        if total == 0:
            continue

        # Pick DOMINANT label for this run!
        if dec > inc and dec > con:
            dominant = 'decreasing'
        elif inc > dec and inc > con:
            dominant = 'increasing'
        else:
            dominant = 'constant'

        pred = generate_predicate_name(
            phase, sensor, dominant)
        predicates.add(pred)

        results.append({
            'run_id':       run_id,
            'example_type': example_type,
            'dominant':     dominant,
            'predicate':    pred,
            'inc':          inc,
            'dec':          dec,
            'con':          con,
        })

    return results, predicates


def generate_bk(run_results):
    """Generates background knowledge."""
    facts = []
    for r in run_results:
        facts.append(
            f'{r["predicate"]}'
            f'({r["run_id"]}).')
    return '\n'.join(facts)


def generate_exs(run_results):
    """Generates examples."""
    pos_examples = []
    neg_examples = []

    for r in run_results:
        if r['example_type'] == 'positive':
            pos_examples.append(
                f'pos(phase_correct'
                f'({r["run_id"]})).')
        else:
            neg_examples.append(
                f'neg(phase_correct'
                f'({r["run_id"]})).')

    return pos_examples, neg_examples


def generate_bias(predicates):
    """Generates bias file."""
    lines = []
    lines.append('head_pred(phase_correct,1).')

    for pred in sorted(predicates):
        lines.append(f'body_pred({pred},1).')

    lines.append('type(phase_correct,(run,)).')
    for pred in sorted(predicates):
        lines.append(f'type({pred},(run,)).')

    lines.append(
        'direction(phase_correct,(in,)).')
    for pred in sorted(predicates):
        lines.append(
            f'direction({pred},(in,)).')

    lines.append('max_clauses(3).')
    lines.append('max_body(1).')
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


def save_results(
        phase, sensor, rules,
        scores, popper_output):
    """Saves results."""
    os.makedirs(RESULTS_DIR, exist_ok=True)

    filename = os.path.join(
        RESULTS_DIR,
        f'{phase}_{sensor}_raw_rules.txt')

    with open(filename, 'w') as f:
        f.write(f'Phase: {phase}\n')
        f.write(f'Sensor: {sensor}\n')
        f.write('Method: RAW DOMINANT DELTA\n')
        f.write(
            f'Delta threshold: '
            f'{DELTA_THRESHOLD}\n')
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

    print(f'  Saved: {filename}')
    return filename


def learn_rules_raw(all_runs, phase, sensor):
    """Learns rules for one phase."""
    print(f'\n--- Sensor: {sensor} ---')

    run_results, predicates = \
        process_all_runs(
            all_runs, phase, sensor)

    if not run_results:
        print('  No data found!')
        return None

    # Show classifications
    for r in run_results:
        print(f'    {r["run_id"]:20s} '
              f'{r["example_type"]:8s} '
              f'inc={r["inc"]:3d} '
              f'dec={r["dec"]:3d} '
              f'con={r["con"]:3d} '
              f'→ {r["dominant"]}')

    pos_examples, neg_examples = \
        generate_exs(run_results)

    print(f'  Positive: {len(pos_examples)}')
    print(f'  Negative: {len(neg_examples)}')

    if not pos_examples or \
       not neg_examples:
        print('  Not enough examples!')
        return None

    bk_content   = generate_bk(run_results)
    bias_content = generate_bias(predicates)

    os.makedirs(POPPER_DIR, exist_ok=True)

    with open(os.path.join(
            POPPER_DIR, 'bk.pl'), 'w') as f:
        f.write(
            f'% Phase: {phase}\n'
            f'% Sensor: {sensor}\n'
            f'% Method: Dominant delta\n\n')
        f.write(bk_content)

    exs_content = (
        '% Positive examples\n' +
        '\n'.join(pos_examples) +
        '\n\n% Negative examples\n' +
        '\n'.join(neg_examples))

    with open(os.path.join(
            POPPER_DIR, 'exs.pl'), 'w') as f:
        f.write(exs_content)

    with open(os.path.join(
            POPPER_DIR, 'bias.pl'), 'w') as f:
        f.write(bias_content)

    print('  Running Popper...')
    popper_output = run_popper()
    rules, scores = extract_solution(
        popper_output)

    if rules:
        print(f'  ✅ SOLUTION FOUND!')
        for rule in rules:
            print(f'    {rule}')
        print(f'  Scores: {scores}')
    else:
        print(f'  ❌ NO SOLUTION')

    save_results(
        phase, sensor, rules,
        scores, popper_output)

    return rules, scores


def generate_summary(all_results):
    """Generates summary."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    summary_path = os.path.join(
        RESULTS_DIR, 'summary_raw.txt')

    with open(summary_path, 'w') as f:
        f.write('ILP PHASE LEARNING SUMMARY\n')
        f.write('Method: RAW DOMINANT DELTA\n')
        f.write('(No QTA — for comparison!)\n')
        f.write('='*60 + '\n\n')
        f.write(
            f'Delta threshold: '
            f'{DELTA_THRESHOLD}\n\n')
        f.write(
            'Method: Count increases/decreases/'
            'constant across all row pairs\n')
        f.write(
            'Pick dominant label per run!\n\n')

        for phase, sensor, rules, scores \
                in all_results:
            f.write(f'Phase: {phase}\n')
            f.write(f'Sensor: {sensor}\n')

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

    print(f'\nSummary: {summary_path}')


# ── MAIN ──────────────────────────────────────────────────────
if __name__ == '__main__':

    print('='*60)
    print('ILP PHASE LEARNER - RAW DOMINANT')
    print('Counts deltas → picks dominant!')
    print('ONE fact per run per phase!')
    print('='*60)

    all_runs = load_all_csv_files()
    print(f'Total runs: {len(all_runs)}')

    all_phase_results = []

    for phase in PHASES:
        print(f'\n\n{"#"*60}')
        print(f'# PHASE: {phase}')
        print(f'{"#"*60}')

        best_result = None
        best_recall = 0
        best_sensor = None

        for sensor in SENSORS_TO_TRY:
            result = learn_rules_raw(
                all_runs, phase, sensor)

            if result is not None:
                rules, scores = result
                if rules:
                    recall = scores.get(
                        'recall', 0)
                    if recall > best_recall:
                        best_recall = recall
                        best_result = (
                            rules, scores)
                        best_sensor = sensor

        if best_result:
            rules, scores = best_result
            print(f'\n✅ Best for {phase}:')
            print(f'   Sensor: {best_sensor}')
            print(f'   Rules: {rules}')
            print(f'   Recall: {best_recall}')
            all_phase_results.append((
                phase, best_sensor,
                rules, scores))
        else:
            print(
                f'\n⚠️ No solution for {phase}!')
            all_phase_results.append((
                phase, 'none', None, {}))

    generate_summary(all_phase_results)

    print('\n' + '='*60)
    print('COMPLETE!')
    print(f'Results: {RESULTS_DIR}')
    print('\nCompare:')
    print('QTA: cat ~/rnd_ws/ilp_results/'
          'summary.txt')
    print('RAW: cat ~/rnd_ws/ilp_results_raw/'
          'summary_raw.txt')
    print('='*60)