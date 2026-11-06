#!/usr/bin/env python3
"""
ILP Phase Learner for Robile Wall Following
============================================
This script:
1. Reads QTA JSON results for each run
2. Creates Prolog facts per action phase
3. Runs Popper ILP for each phase
4. Saves learned rules to ilp_results/

Author: Alisha Syed Karimulla
Project: Qualitative Analysis of Robotic
         Signal Components using ILP
"""

import json
import os
import subprocess


# ── CONFIGURATION ─────────────────────────────────────────────
QTA_DIR     = os.path.expanduser('~/rnd_ws/qta_results')
POPPER_DIR  = os.path.expanduser('~/rnd_ws/popper_run')
# RESULTS_DIR = os.path.expanduser('~/rnd_ws/ilp_results')
RESULTS_DIR = os.path.expanduser('~/rnd_ws/ilp_results_qta_plain')
POPPER_PATH = os.path.expanduser('~/Popper/popper.py')
PYTHON_PATH = os.path.expanduser('~/popper_env/bin/python')

# ALL phases to learn rules for
PHASES = [
    'approaching_wall',
    'wall_following',
    'obstacle_detected',
    'obstacle_avoidance',
    'wall_reacquired',
    'wall_following_fail',
    'searching_wall',
]

# Expected QTA shape per phase
# This is what the sensor SHOULD show
# during each phase in a correct run
PHASE_EXPECTED = {
    'approaching_wall':    'is_decreasing',
    'wall_following':      'is_constant',
    'obstacle_detected':   'is_decreasing',
    'obstacle_avoidance':  'is_increasing',
    'wall_reacquired':     'is_decreasing',
    'wall_following_fail': 'is_oscillating',
    'searching_wall':      'is_oscillating',
}

# Sensors to try for each phase
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
# ──────────────────────────────────────────────────────────────


# def load_all_qta_results():
#     """Loads all QTA JSON files."""
#     results = []
#     files = sorted([
#         f for f in os.listdir(QTA_DIR)
#         if f.endswith('_qta.json')])

#     for filename in files:
#         filepath = os.path.join(QTA_DIR, filename)
#         with open(filepath, 'r') as f:
#             result = json.load(f)
#             results.append(result)

#     print(f'Loaded {len(results)} QTA result files')
#     return results



# def load_all_qta_results():
#     """Loads ONLY good run QTA JSON files!"""
#     results = []
#     files = sorted([
#         f for f in os.listdir(QTA_DIR)
#         if f.endswith('_qta.json')])

#     for filename in files:
#         filepath = os.path.join(QTA_DIR, filename)
#         with open(filepath, 'r') as f:
#             result = json.load(f)
#             # ONLY load good runs for training!
#             if result.get('example_type') == 'positive':
#                 results.append(result)

#     print(f'Loaded {len(results)} GOOD run QTA files')
#     return results


def load_all_qta_results():
    """Loads ONLY plain wall good run QTA JSON files!"""
    results = []
    files = sorted([
        f for f in os.listdir(QTA_DIR)
        if f.endswith('_qta.json')])

    for filename in files:
        # Task 1: Plain wall good runs only!
        if 'pw' in filename and 'good' in filename:
            filepath = os.path.join(QTA_DIR, filename)
            with open(filepath, 'r') as f:
                result = json.load(f)
                results.append(result)

    print(f'Loaded {len(results)} plain wall good run QTA files')
    return results

def get_shape_for_phase(result, phase, sensor):
    """
    Gets QTA shape for a specific phase
    and sensor from one run's results.
    """
    windows     = result.get('windows', {})
    phase_data  = windows.get(phase, {})
    sensor_data = phase_data.get(sensor, {})
    shape = sensor_data.get('shape', None)
    return shape


def generate_predicate_name(
        phase, sensor, shape):
    """
    Converts phase + sensor + shape
    into a Prolog predicate name.
    """
    phase_short = {
        'approaching_wall':    'approach',
        'wall_following':      'wf',
        'wall_following_fail': 'fail',
        'obstacle_detected':   'detect',
        'obstacle_avoidance':  'avoid',
        'wall_reacquired':     'reacquire',
        'searching_wall':      'search',
        'idle':                'idle',
    }.get(phase, phase[:6])

    sensor_short = {
        'lidar_left':    'lidar',
        'lidar_right':   'lidar_right',
        'lidar_front':   'lidar_front',
        'imu_angular_z': 'imu',
        'imu_accel_x':   'imu_x',
        'imu_accel_y':   'imu_y',
        'odom_linear_x': 'odom',
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


def generate_bk_for_phase(
        results, phase, sensor):
    """
    Generates background knowledge facts
    for one specific phase and sensor.
    """
    facts = []
    facts.append('% Background Knowledge')
    facts.append(f'% Phase: {phase}')
    facts.append(f'% Sensor: {sensor}')
    facts.append(
        '% Generated by ilp_phase_learner.py\n')

    predicates_used = set()

    for result in results:
        run_id = result['run_id']
        shape  = get_shape_for_phase(
            result, phase, sensor)

        if shape is None:
            continue

        pred = generate_predicate_name(
            phase, sensor, shape)
        predicates_used.add(pred)

        fact = f'{pred}({run_id}).'
        facts.append(fact)

    return '\n'.join(facts), predicates_used


def generate_exs_for_phase(
        results, phase, sensor):
    """
    Generates positive and negative examples
    based on expected QTA shape per phase.

    pos = runs where sensor shape matches
          expected shape for this phase
    neg = runs where sensor shape does NOT
          match expected shape
    """
    pos_examples = []
    neg_examples = []

    expected_shape = PHASE_EXPECTED.get(phase)

    for result in results:
        run_id  = result['run_id']
        windows = result.get('windows', {})

        # Only include runs that HAVE this phase
        if phase not in windows:
            continue

        actual_shape = get_shape_for_phase(
            result, phase, sensor)

        if actual_shape is None:
            continue

        # pos = matches expected shape!
        if actual_shape == expected_shape:
            pos_examples.append(
                f'pos(phase_correct({run_id})).')
        else:
            # neg = does NOT match expected!
            neg_examples.append(
                f'neg(phase_correct({run_id})).')

    return pos_examples, neg_examples


def generate_bias_for_phase(predicates_used):
    """Generates bias file for Popper."""
    lines = []
    lines.append('head_pred(phase_correct,1).')

    for pred in sorted(predicates_used):
        lines.append(f'body_pred({pred},1).')

    lines.append('type(phase_correct,(run,)).')
    for pred in sorted(predicates_used):
        lines.append(f'type({pred},(run,)).')

    lines.append(
        'direction(phase_correct,(in,)).')
    for pred in sorted(predicates_used):
        lines.append(
            f'direction({pred},(in,)).')

    lines.append('max_clauses(3).')
    lines.append('max_body(1).')
    lines.append('max_vars(1).')

    return '\n'.join(lines)


def run_popper(timeout=120):
    """Runs Popper ILP and returns output."""
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
    """Extracts learned rules from output."""
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


def save_results(phase, sensor, rules,
                 scores, popper_output):
    """Saves results for one phase."""
    os.makedirs(RESULTS_DIR, exist_ok=True)

    filename = os.path.join(
        RESULTS_DIR,
        f'{phase}_{sensor}_rules.txt')

    with open(filename, 'w') as f:
        f.write(f'Phase: {phase}\n')
        f.write(f'Sensor: {sensor}\n')
        f.write(
            f'Expected shape: '
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

    print(f'  Saved: {filename}')
    return filename


def learn_rules_for_phase(
        results, phase, sensor):
    """
    Learns rules for one phase and sensor.
    """
    print(f'\n{"="*60}')
    print(f'Phase: {phase} | Sensor: {sensor}')
    print(f'Expected: {PHASE_EXPECTED.get(phase)}')
    print('='*60)

    # Generate background knowledge
    bk_content, predicates_used = \
        generate_bk_for_phase(
            results, phase, sensor)

    if not predicates_used:
        print(f'  No facts found!')
        return None

    # Generate examples
    pos_examples, neg_examples = \
        generate_exs_for_phase(
            results, phase, sensor)

    print(f'  Positive: {len(pos_examples)}')
    print(f'  Negative: {len(neg_examples)}')

    if not pos_examples or not neg_examples:
        print(f'  Not enough examples!')
        # Save empty result
        save_results(
            phase, sensor, None,
            {}, 'NOT ENOUGH EXAMPLES')
        return None

    # Generate bias
    bias_content = generate_bias_for_phase(
        predicates_used)

    # Write files
    os.makedirs(POPPER_DIR, exist_ok=True)

    with open(os.path.join(
            POPPER_DIR, 'bk.pl'), 'w') as f:
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

    # Run Popper
    popper_output = run_popper()

    # Extract solution
    rules, scores = extract_solution(
        popper_output)

    if rules:
        print(f'  ✅ SOLUTION FOUND!')
        for rule in rules:
            print(f'    {rule}')
        print(f'  Scores: {scores}')
    else:
        print(f'  ❌ NO SOLUTION')

    # Save results
    save_results(
        phase, sensor, rules,
        scores, popper_output)

    return rules, scores


def generate_summary(all_results):
    """Generates a summary of all rules."""
    summary_path = os.path.join(
        RESULTS_DIR, 'summary.txt')

    with open(summary_path, 'w') as f:
        f.write('ILP PHASE LEARNING SUMMARY\n')
        f.write('Robile Wall Following\n')
        f.write('='*60 + '\n\n')

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

    print(f'\nSummary saved: {summary_path}')


# ── MAIN ──────────────────────────────────────────────────────
if __name__ == '__main__':

    print('='*60)
    print('ILP PHASE LEARNER')
    print('Robile Wall Following')
    print('='*60)

    # Load all QTA results
    results = load_all_qta_results()

    # Learn rules for each phase
    # Try ALL sensors for each phase
    all_phase_results = []

    for phase in PHASES:
        print(f'\n\n{"#"*60}')
        print(f'# PHASE: {phase}')
        print(f'{"#"*60}')

        best_result = None
        best_recall = 0

        for sensor in SENSORS_TO_TRY:
            result = learn_rules_for_phase(
                results, phase, sensor)

            if result is not None:
                rules, scores = result
                if rules:
                    recall = scores.get(
                        'recall', 0)
                    # Keep best recall result
                    if recall > best_recall:
                        best_recall = recall
                        best_result = (
                            phase, sensor,
                            rules, scores)

        if best_result:
            all_phase_results.append(
                best_result)
            print(f'\n  ✅ Best rule for {phase}:')
            print(f'     Sensor: {best_result[1]}')
            print(f'     Rules: {best_result[2]}')
            print(f'     Recall: {best_recall}')
        else:
            print(f'\n  ⚠️ No solution for {phase}!')
            all_phase_results.append((
                phase, 'none', None, {}))

    # Generate summary
    generate_summary(all_phase_results)

    print('\n' + '='*60)
    print('COMPLETE!')
    print(f'Results in: {RESULTS_DIR}')
    print('='*60)