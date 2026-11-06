#!/usr/bin/env python3
"""
ILP Phase Learner WITHOUT QTA (Raw)
=====================================
FAIR COMPARISON with QTA method!

Uses SAME example logic as QTA:
pos = runs where RAW label matches
      expected shape for this phase!
neg = runs where RAW label does NOT
      match expected shape!

KEY DIFFERENCE FROM QTA:
QTA: normalized slope / mean → label
RAW: ratio of delta counts → label

Author: Alisha Syed Karimulla
Project: Qualitative Analysis of Robotic
         Signal Components using ILP
"""

import os
import subprocess
import pandas as pd
import numpy as np
from collections import Counter


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

# Expected shape per phase
# Same as QTA script!
# Based on domain knowledge of
# robot wall following behavior!
PHASE_EXPECTED = {
    'approaching_wall':    'is_decreasing',
    'wall_following':      'is_constant',
    'obstacle_detected':   'is_decreasing',
    'obstacle_avoidance':  'is_increasing',
    'wall_reacquired':     'is_decreasing',
    'wall_following_fail': 'is_oscillating',
    'searching_wall':      'is_oscillating',
}

# RAW classification thresholds
DELTA_THRESHOLD       = 0.01
ZERO_THRESHOLD        = 0.02
CONSTANT_RATIO        = 0.60
OSCILLATING_INC_RATIO = 0.20
OSCILLATING_DEC_RATIO = 0.20
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


def classify_raw_5labels(values):
    """
    Classifies signal using 5 labels
    using ratio of delta counts.

    KEY DIFFERENCE FROM QTA:
    QTA: normalized_slope = slope/mean
    RAW: ratio of inc/dec/con counts
    """
    values = np.array(values, dtype=float)
    values = values[~np.isnan(values)]
    values = values[values != 0.0]

    if len(values) < 3:
        return None

    mean_val = np.mean(np.abs(values))

    inc = dec = con = 0
    for i in range(len(values) - 1):
        delta = values[i+1] - values[i]
        if delta > DELTA_THRESHOLD:
            inc += 1
        elif delta < -DELTA_THRESHOLD:
            dec += 1
        else:
            con += 1

    total = inc + dec + con
    if total == 0:
        return None

    ir = inc / total
    dr = dec / total
    cr = con / total

    # Label 1: is_zero
    if mean_val < ZERO_THRESHOLD:
        return 'is_zero'

    # Label 2: is_constant
    if cr > CONSTANT_RATIO:
        return 'is_constant'

    # Label 3: is_oscillating
    if (ir > OSCILLATING_INC_RATIO
            and dr > OSCILLATING_DEC_RATIO):
        return 'is_oscillating'

    # Label 4: is_decreasing
    if dr > ir:
        return 'is_decreasing'

    # Label 5: is_increasing
    return 'is_increasing'


def generate_predicate_name(
        phase, sensor, shape):
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

    shape_short = {
        'is_constant':    'constant',
        'is_increasing':  'increasing',
        'is_decreasing':  'decreasing',
        'is_oscillating': 'oscillating',
        'is_zero':        'zero',
    }.get(shape, shape)

    return (f'{phase_short}_'
            f'{sensor_short}_'
            f'{shape_short}')


def process_all_runs(
        all_runs, phase, sensor):
    """
    For each run:
    1. Extract phase window from CSV
    2. Calculate RAW label
    3. Compare with EXPECTED shape
    4. pos = matches expected
       neg = does not match
    """
    results    = []
    predicates = set()

    expected = PHASE_EXPECTED.get(phase)

    for run in all_runs:
        run_id       = run['run_id']
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
        shape  = classify_raw_5labels(values)

        if shape is None:
            continue

        pred = generate_predicate_name(
            phase, sensor, shape)
        predicates.add(pred)

        # SAME logic as QTA!
        # pos = matches expected shape!
        # neg = does not match!
        if shape == expected:
            example_type = 'positive'
        else:
            example_type = 'negative'

        results.append({
            'run_id':       run_id,
            'example_type': example_type,
            'shape':        shape,
            'predicate':    pred,
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
        f.write('Method: RAW 5-LABEL\n')
        f.write(
            f'Expected: '
            f'{PHASE_EXPECTED.get(phase)}\n')
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

    return filename


def learn_rules_raw(all_runs, phase, sensor):
    """Learns rules for one phase."""
    print(f'\n--- Sensor: {sensor} ---')
    print(f'    Expected: '
          f'{PHASE_EXPECTED.get(phase)}')

    run_results, predicates = \
        process_all_runs(
            all_runs, phase, sensor)

    if not run_results:
        print('  No data found!')
        return None

    # Show classifications
    for r in run_results:
        match = '✅' if r['example_type'] \
            == 'positive' else '❌'
        print(f'    {r["run_id"]:20s} '
              f'{r["shape"]:15s} {match}')

    pos_examples, neg_examples = \
        generate_exs(run_results)

    print(f'  pos={len(pos_examples)} '
          f'neg={len(neg_examples)}')

    if not pos_examples or \
       not neg_examples:
        print('  Not enough examples!')
        save_results(
            phase, sensor, None,
            {}, 'NOT ENOUGH EXAMPLES')
        return None

    os.makedirs(POPPER_DIR, exist_ok=True)

    with open(os.path.join(
            POPPER_DIR, 'bk.pl'), 'w') as f:
        f.write(generate_bk(run_results))

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
        f.write(generate_bias(predicates))

    print('  Running Popper...')
    popper_output = run_popper()
    rules, scores = extract_solution(
        popper_output)

    if rules:
        print(f'  ✅ SOLUTION!')
        for rule in rules:
            print(f'    {rule}')
        print(f'  {scores}')
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
        f.write('Method: RAW 5-LABEL\n')
        f.write('(For comparison with QTA!)\n')
        f.write('='*60 + '\n\n')
        f.write('Example logic (SAME as QTA):\n')
        f.write(
            'pos = RAW label matches '
            'expected shape!\n')
        f.write(
            'neg = RAW label does NOT '
            'match expected shape!\n\n')
        f.write('Expected shapes:\n')
        for phase, shape in \
                PHASE_EXPECTED.items():
            f.write(f'  {phase}: {shape}\n')
        f.write('\n')

        for phase, sensor, rules, scores \
                in all_results:
            f.write(f'Phase: {phase}\n')
            f.write(f'Sensor: {sensor}\n')
            f.write(
                f'Expected: '
                f'{PHASE_EXPECTED.get(phase)}\n')

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
    print('ILP PHASE LEARNER - RAW 5-LABEL')
    print('FAIR COMPARISON WITH QTA!')
    print('Same example logic as QTA!')
    print('pos = matches expected shape!')
    print('neg = does not match!')
    print('='*60)

    all_runs = load_all_csv_files()
    print(f'Total runs: {len(all_runs)}')

    all_phase_results = []

    for phase in PHASES:
        print(f'\n\n{"#"*60}')
        print(f'# PHASE: {phase}')
        print(f'# Expected: '
              f'{PHASE_EXPECTED.get(phase)}')
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