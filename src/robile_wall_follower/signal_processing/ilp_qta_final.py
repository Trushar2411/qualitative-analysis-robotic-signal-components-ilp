#!/usr/bin/env python3
"""
ILP Phase Learner - QTA Final
===============================
Same logic as ilp_phase_learner.py BUT:
1. Good runs only!
2. ALL sensors together per phase!
3. Popper finds multi-sensor rules!

Change TASK and RESULTS_DIR for each run:
TASK = 'pw'   → plain wall good runs
TASK = 'pill' → pillar wall good runs
TASK = 'all'  → combined good runs

Author: Alisha Syed Karimulla
Project: Qualitative Analysis of Robotic
         Signal Components using ILP
"""

import json
import os
import subprocess


# ── CONFIGURATION ─────────────────────────────────────────────
QTA_DIR     = os.path.expanduser(
    '~/rnd_ws/qta_results')
POPPER_DIR  = os.path.expanduser(
    '~/rnd_ws/popper_run')
POPPER_PATH = os.path.expanduser(
    '~/Popper/popper.py')
PYTHON_PATH = os.path.expanduser(
    '~/popper_env/bin/python')

# ── CHANGE THESE FOR EACH TASK ────────────────────────────────
TASK        = 'pw'
RESULTS_DIR = os.path.expanduser(
    '~/rnd_ws/ilp_results_qta_plain')
# TASK        = 'pill'
# RESULTS_DIR = os.path.expanduser(
#     '~/rnd_ws/ilp_results_qta_pillar')
# TASK        = 'all'
# RESULTS_DIR = os.path.expanduser(
#     '~/rnd_ws/ilp_results_qta_combined')
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

# Expected QTA shape per phase
# Same as ilp_phase_learner.py!
PHASE_EXPECTED = {
    'approaching_wall':    'is_decreasing',
    'wall_following':      'is_constant',
    'obstacle_detected':   'is_decreasing',
    'obstacle_avoidance':  'is_increasing',
    'wall_reacquired':     'is_decreasing',
    'wall_following_fail': 'is_oscillating',
    'searching_wall':      'is_oscillating',
}

# ALL sensors!
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
    """
    Loads QTA JSON files!
    Good runs only!
    Filtered by task!
    """
    results = []
    files = sorted([
        f for f in os.listdir(QTA_DIR)
        if f.endswith('_qta.json')])

    for filename in files:
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

        filepath = os.path.join(
            QTA_DIR, filename)
        with open(filepath, 'r') as f:
            result = json.load(f)
            results.append(result)

    print(f'Loaded {len(results)} good run '
          f'QTA files for task={TASK}')
    return results


def get_shape(result, phase, sensor):
    """Gets QTA shape for phase and sensor."""
    windows = result.get('windows', {})
    if phase not in windows:
        return None
    return windows[phase].get(
        sensor, {}).get('shape', None)


def get_pred_name(phase, sensor, shape):
    """Creates predicate name."""
    p = {
        'approaching_wall':    'approach',
        'wall_following':      'wf',
        'obstacle_detected':   'detect',
        'obstacle_avoidance':  'avoid',
        'wall_reacquired':     'reacquire',
        'wall_following_fail': 'fail',
        'searching_wall':      'search',
    }.get(phase, phase[:6])

    s = {
        'lidar_left':        'lidar',
        'lidar_right':       'lidar_r',
        'lidar_front':       'lidar_f',
        'lidar_front_right': 'lidar_fr',
        'imu_accel_x':       'imu_x',
        'imu_accel_y':       'imu_y',
        'imu_angular_z':     'imu',
        'odom_linear_x':     'odom',
    }.get(sensor, sensor[:5])

    sh = {
        'is_constant':    'constant',
        'is_increasing':  'increasing',
        'is_decreasing':  'decreasing',
        'is_oscillating': 'oscillating',
        'is_zero':        'zero',
    }.get(shape, shape)

    return f'{p}_{s}_{sh}'

# def get_pred_name(sensor, shape):
#     """No phase name! Just sensor + shape!"""
#     s = {
#         'lidar_left':        'lidar',
#         'lidar_right':       'lidar_r',
#         'lidar_front':       'lidar_f',
#         'lidar_front_right': 'lidar_fr',
#         'imu_accel_x':       'imu_x',
#         'imu_accel_y':       'imu_y',
#         'imu_angular_z':     'imu',
#         'odom_linear_x':     'odom',
#     }.get(sensor, sensor[:5])

#     sh = {
#         'is_constant':    'constant',
#         'is_increasing':  'increasing',
#         'is_decreasing':  'decreasing',
#         'is_oscillating': 'oscillating',
#         'is_zero':        'zero',
#     }.get(shape, shape)

#     return f'{s}_{sh}'

def generate_bias(predicates):
    """
    Generates bias file!
    Allows multi-sensor combinations!
    max_body(4) = up to 4 sensors per rule!
    """
    lines = []
    lines.append('head_pred(phase_correct,1).')
    for pred in sorted(predicates):
        lines.append(f'body_pred({pred},1).')
    lines.append(
        'type(phase_correct,(run,)).')
    for pred in sorted(predicates):
        lines.append(
            f'type({pred},(run,)).')
    lines.append(
        'direction(phase_correct,(in,)).')
    for pred in sorted(predicates):
        lines.append(
            f'direction({pred},(in,)).')
    # Allow up to 4 sensors per rule!
    lines.append('max_clauses(3).')
    lines.append('max_body(4).')
    lines.append('max_vars(1).')
    return '\n'.join(lines)


def run_popper(timeout=120):
    """Runs Popper ILP."""
    cmd = [
        PYTHON_PATH, POPPER_PATH,
        POPPER_DIR, '--stats',
        '--timeout', str(timeout)
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True)
    return result.stdout + result.stderr


def extract_solution(output):
    """Extracts rules and scores."""
    lines  = output.split('\n')
    rules  = []
    scores = {}
    in_sol = False

    for line in lines:
        if '** SOLUTION **' in line:
            in_sol = True
            continue
        if in_sol and '****' in line:
            in_sol = False
            continue
        if in_sol and line.strip():
            if 'Precision' in line:
                for p in line.split():
                    if 'Precision:' in p:
                        scores['precision'] = \
                            float(p.split(':')[1])
                    if 'Recall:' in p:
                        scores['recall'] = \
                            float(p.split(':')[1])
                    if 'TP:' in p:
                        scores['tp'] = \
                            int(p.split(':')[1])
                    if 'FN:' in p:
                        scores['fn'] = \
                            int(p.split(':')[1])
            elif 'phase_correct' in line:
                rules.append(line.strip())

    if 'NO SOLUTION' in output:
        return None, {}
    return rules, scores


# def learn_phase(results, phase):
#     """
#     Learns rules for one phase!
#     Uses ALL sensors together!

#     Same pos/neg logic as
#     ilp_phase_learner.py:
#     pos = runs where expected shape found
#     neg = runs where expected shape NOT found
#     """
#     expected   = PHASE_EXPECTED[phase]
#     facts      = []
#     pos_exs    = []
#     neg_exs    = []
#     predicates = set()

#     for result in results:
#         run_id  = result['run_id']
#         windows = result.get('windows', {})

#         # Only runs that HAVE this phase!
#         if phase not in windows:
#             continue

#         # Create facts for ALL sensors!
#         shapes_found = []
#         for sensor in ALL_SENSORS:
#             shape = get_shape(
#                 result, phase, sensor)
#             if shape is None:
#                 continue
#             # pred = get_pred_name(
#             #     phase, sensor, shape)
#             pred = get_pred_name(
#                 sensor, shape)
#             predicates.add(pred)
#             facts.append(
#                 f'{pred}({run_id}).')
#             shapes_found.append(shape)

#         # pos = expected shape found!
#         # neg = expected shape NOT found!
#         # Same as ilp_phase_learner.py!
#         if expected in shapes_found:
#             pos_exs.append(
#                 f'pos(phase_correct'
#                 f'({run_id})).')
#         else:
#             neg_exs.append(
#                 f'neg(phase_correct'
#                 f'({run_id})).')

#     return facts, pos_exs, neg_exs, predicates

def learn_phase(results, phase):
    """
    Uses original pos/neg logic!
    pos = runs where expected shape found!
    neg = runs where expected shape NOT found!
    """
    expected   = PHASE_EXPECTED[phase]
    facts      = []
    pos_exs    = []
    neg_exs    = []
    predicates = set()

    for result in results:
        run_id  = result['run_id']
        windows = result.get('windows', {})

        # Only runs that HAVE this phase!
        if phase not in windows:
            continue

        # Create facts for ALL sensors!
        shapes_found = []
        for sensor in ALL_SENSORS:
            shape = windows[phase].get(
                sensor, {}).get('shape', None)
            if shape is None:
                continue
            pred = get_pred_name(
                phase, sensor, shape)
            predicates.add(pred)
            facts.append(
                f'{pred}({run_id}).')
            shapes_found.append(shape)

        # pos = expected shape found!
        # neg = expected shape NOT found!
        if expected in shapes_found:
            pos_exs.append(
                f'pos(phase_correct({run_id})).')
        else:
            neg_exs.append(
                f'neg(phase_correct({run_id})).')

    return facts, pos_exs, neg_exs, predicates

# def learn_phase(results, phase):
#     """
#     Learns rules for one phase!
#     Uses ALL sensors together!

#     pos = run-phase WHERE phase = target!
#     neg = run-phase WHERE phase != target!

#     Good runs only!
#     Different phases provide contrast! ✅
#     """
#     facts      = []
#     pos_exs    = []
#     neg_exs    = []
#     predicates = set()

#     for result in results:
#         run_id  = result['run_id']
#         windows = result.get('windows', {})

#         for current_phase, phase_data \
#                 in windows.items():
#             # Skip idle phase!
#             if current_phase == 'idle':
#                 continue

#             # Unique state per run+phase!
#             state_id = (
#                 f'{run_id}_{current_phase}')

#             # Create facts for ALL sensors!
#             any_fact = False
#             for sensor in ALL_SENSORS:
#                 shape = phase_data.get(
#                     sensor, {}).get(
#                     'shape', None)
#                 if shape is None:
#                     continue
#                 # pred = get_pred_name(
#                 #     sensor, shape)
#                 pred = get_pred_name(
#                     current_phase, sensor, shape)
#                 predicates.add(pred)
#                 facts.append(
#                     f'{pred}({state_id}).')
#                 any_fact = True

#             if not any_fact:
#                 continue

#             # pos = target phase!
#             # neg = other phases!
#             if current_phase == phase:
#                 pos_exs.append(
#                     f'pos(phase_correct'
#                     f'({state_id})).')
#             else:
#                 neg_exs.append(
#                     f'neg(phase_correct'
#                     f'({state_id})).')

#     return facts, pos_exs, neg_exs, predicates


def save_results(
        phase, rules, scores, output):
    """Saves results."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(
        RESULTS_DIR,
        f'{phase}_rules.txt')

    with open(path, 'w') as f:
        f.write(f'Phase: {phase}\n')
        f.write(f'Task: {TASK}\n')
        f.write('Method: QTA MULTI-SENSOR\n')
        f.write('Good runs only!\n')
        f.write('='*50 + '\n\n')
        if rules:
            f.write('LEARNED RULES:\n')
            for r in rules:
                f.write(f'  {r}\n')
            f.write('\nSCORES:\n')
            for k, v in scores.items():
                f.write(f'  {k}: {v}\n')
        else:
            f.write('NO SOLUTION\n')
        f.write('\n\nFULL OUTPUT:\n')
        f.write(output)


def generate_summary(all_results):
    """Generates summary."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(
        RESULTS_DIR, 'summary.txt')

    with open(path, 'w') as f:
        f.write('ILP PHASE LEARNING SUMMARY\n')
        f.write(f'Task: {TASK}\n')
        f.write('Method: QTA MULTI-SENSOR\n')
        f.write('Good runs only!\n')
        f.write('='*60 + '\n\n')

        for phase, rules, scores \
                in all_results:
            f.write(f'Phase: {phase}\n')
            f.write(
                f'Expected: '
                f'{PHASE_EXPECTED[phase]}\n')
            if rules:
                f.write('Rules:\n')
                for r in rules:
                    f.write(f'  {r}\n')
                f.write(
                    f'Precision: '
                    f'{scores.get("precision","N/A")}\n')
                f.write(
                    f'Recall: '
                    f'{scores.get("recall","N/A")}\n')
            else:
                f.write('NO SOLUTION\n')
            f.write('\n')

    print(f'Summary saved: {path}')


# ── MAIN ──────────────────────────────────────────────────────
if __name__ == '__main__':

    print('='*60)
    print('ILP PHASE LEARNER - QTA FINAL')
    print(f'Task: {TASK}')
    print('Good runs only!')
    print('ALL sensors combined!')
    print('Popper finds multi-sensor rules!')
    print('='*60)

    results = load_qta_results()
    all_phase_results = []

    for phase in PHASES:
        print(f'\n{"#"*50}')
        print(f'# PHASE: {phase}')
        print(f'{"#"*50}')

        (facts, pos_exs,
         neg_exs, predicates) = \
            learn_phase(results, phase)

        print(f'pos={len(pos_exs)} '
              f'neg={len(neg_exs)}')

        if not pos_exs or not neg_exs:
            print('Not enough examples!')
            all_phase_results.append(
                (phase, None, {}))
            continue

        os.makedirs(POPPER_DIR, exist_ok=True)

        with open(os.path.join(
                POPPER_DIR, 'bk.pl'), 'w') as f:
            f.write('\n'.join(facts))

        exs = (
            '% Positive\n' +
            '\n'.join(pos_exs) +
            '\n\n% Negative\n' +
            '\n'.join(neg_exs))

        with open(os.path.join(
                POPPER_DIR, 'exs.pl'), 'w') as f:
            f.write(exs)

        with open(os.path.join(
                POPPER_DIR, 'bias.pl'), 'w') as f:
            f.write(generate_bias(predicates))

        print('Running Popper...')
        output = run_popper()
        rules, scores = extract_solution(output)

        if rules:
            print('✅ SOLUTION FOUND!')
            for r in rules:
                print(f'  {r}')
            print(f'Scores: {scores}')
        else:
            print('❌ NO SOLUTION')

        save_results(
            phase, rules, scores, output)
        all_phase_results.append(
            (phase, rules, scores))

    generate_summary(all_phase_results)

    print('\n' + '='*60)
    print('COMPLETE!')
    print(f'Results: {RESULTS_DIR}')
    print('='*60)