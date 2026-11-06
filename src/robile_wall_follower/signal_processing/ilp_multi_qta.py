#!/usr/bin/env python3
"""
ILP Multi-Sensor Phase Learner - QTA
======================================
Same approach as Trushar but WITH QTA!

For EACH phase:
- Uses QTA normalized slope per sensor
- pos = runs WITH this phase
- neg = runs WITHOUT this phase
- Popper finds COMBINATION of sensors!

Key difference from RAW:
RAW: row by row delta → noisy labels
QTA: normalized slope → clean labels

Author: Alisha Syed Karimulla
Project: Qualitative Analysis of Robotic
         Signal Components using ILP
"""

import json
import os
import subprocess
import pandas as pd
import numpy as np


# ── CONFIGURATION ─────────────────────────────────────────────
QTA_DIR     = os.path.expanduser(
    '~/rnd_ws/qta_results')
DATA_DIR    = os.path.expanduser(
    '~/rnd_ws/data_cleaned')
POPPER_DIR  = os.path.expanduser(
    '~/rnd_ws/popper_run')
RESULTS_DIR = os.path.expanduser(
    '~/rnd_ws/ilp_results_multi_qta')
POPPER_PATH = os.path.expanduser(
    '~/Popper/popper.py')
PYTHON_PATH = os.path.expanduser(
    '~/popper_env/bin/python')

PHASES = [
    'approaching_wall',
    'wall_following',
    'obstacle_detected',
    'obstacle_avoidance',
    'wall_reacquired',
    'wall_following_fail',
    'searching_wall',
]

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
# ──────────────────────────────────────────────────────────────


def load_qta_results():
    """Loads all QTA JSON files."""
    results   = []
    json_files = sorted([
        f for f in os.listdir(QTA_DIR)
        if f.endswith('_qta.json')])

    print(f'Found {len(json_files)} QTA files')

    for filename in json_files:
        try:
            with open(os.path.join(
                    QTA_DIR, filename)) as f:
                results.append(json.load(f))
        except Exception as e:
            print(f'  ERROR: {filename}: {e}')

    print(f'Loaded {len(results)} QTA results')
    return results


def generate_pred_name(sensor, shape):
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

    shape_short = {
        'is_constant':    'constant',
        'is_increasing':  'increasing',
        'is_decreasing':  'decreasing',
        'is_oscillating': 'oscillating',
        'is_zero':        'zero',
    }.get(shape, shape)

    return f'{sensor_short}_{shape_short}'


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
    # Allow combinations of sensors!
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
        qta_results, target_phase):
    """
    Generates Prolog facts using QTA!
    ALL sensors combined!

    For each run:
    If run HAS target phase:
        → Get QTA shape for ALL sensors
        → Create facts for ALL sensors
        → pos example!

    If run does NOT have target phase:
        → Get QTA shapes from other phases
        → Create facts for ALL sensors
        → neg example!

    ONE fact per sensor per run!
    Much cleaner than row by row!
    """
    facts        = []
    pos_examples = []
    neg_examples = []
    predicates   = set()

    for result in qta_results:
        run_id  = result['run_id']
        windows = result.get('windows', {})

        has_phase = target_phase in windows

        if has_phase:
            # Create facts for ALL sensors
            # from target phase!
            added_any = False
            for sensor in ALL_SENSORS:
                shape = windows.get(
                    target_phase, {}).get(
                    sensor, {}).get(
                    'shape', None)

                if shape is None:
                    continue

                pred = generate_pred_name(
                    sensor, shape)
                predicates.add(pred)
                facts.append(
                    f'{pred}({run_id}).')
                added_any = True

            if added_any:
                pos_examples.append(
                    f'pos(phase_correct'
                    f'({run_id})).')

        else:
            # Create facts from other phases!
            added_any = False
            for sensor in ALL_SENSORS:
                shape = None
                for other_phase in PHASES:
                    if other_phase == target_phase:
                        continue
                    s = windows.get(
                        other_phase, {}).get(
                        sensor, {}).get(
                        'shape', None)
                    if s is not None:
                        shape = s
                        break

                if shape is None:
                    continue

                pred = generate_pred_name(
                    sensor, shape)
                predicates.add(pred)
                facts.append(
                    f'{pred}({run_id}).')
                added_any = True

            if added_any:
                neg_examples.append(
                    f'neg(phase_correct'
                    f'({run_id})).')

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
        f.write('Method: QTA MULTI-SENSOR\n')
        f.write('All sensors combined!\n')
        f.write('Uses QTA normalized slope!\n')
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
        RESULTS_DIR, 'summary_qta.txt')

    with open(path, 'w') as f:
        f.write('ILP MULTI-SENSOR SUMMARY\n')
        f.write('Method: QTA MULTI-SENSOR\n')
        f.write('='*60 + '\n\n')
        f.write('With QTA signal processing!\n')
        f.write('All sensors combined!\n')
        f.write('pos = runs WITH phase\n')
        f.write('neg = runs WITHOUT phase\n\n')

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
    print('ILP MULTI-SENSOR - QTA')
    print('With QTA signal processing!')
    print('ALL sensors combined!')
    print('pos = runs WITH phase')
    print('neg = runs WITHOUT phase')
    print('='*60)

    qta_results = load_qta_results()

    all_phase_results = []

    for phase in PHASES:
        print(f'\n\n{"#"*60}')
        print(f'# PHASE: {phase}')
        print(f'{"#"*60}')

        (facts, pos_examples,
         neg_examples,
         predicates) = \
            generate_facts_for_phase(
                qta_results, phase)

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