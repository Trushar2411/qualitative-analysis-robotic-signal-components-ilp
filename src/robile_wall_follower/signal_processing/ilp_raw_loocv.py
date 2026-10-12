#!/usr/bin/env python3
"""
ILP Phase Learner - RAW Dominant (10 Runs)
==========================================
Same approach as Trushar's run_all_phases_10_times.sh!

For each phase:
- Runs Popper 10 times with same data!
- Checks which rule is most consistent!
- Uses dominant label per run per phase!
- ALL sensors combined!
- Good runs only!

Change TASK and RESULTS_DIR for each task:
TASK = 'pw'   → plain wall good runs
TASK = 'pill' → pillar wall good runs
TASK = 'all'  → combined good runs

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
POPPER_PATH = os.path.expanduser(
    '~/Popper/popper.py')
PYTHON_PATH = os.path.expanduser(
    '~/popper_env/bin/python')

# ── CHANGE THESE FOR EACH TASK ────────────────────────────────
TASK        = 'pw'
RESULTS_DIR = os.path.expanduser(
    '~/rnd_ws/ilp_results_raw_10runs_plain')
# TASK        = 'pill'
# RESULTS_DIR = os.path.expanduser(
#     '~/rnd_ws/ilp_results_raw_10runs_pillar')
# TASK        = 'all'
# RESULTS_DIR = os.path.expanduser(
#     '~/rnd_ws/ilp_results_raw_10runs_combined')
# ──────────────────────────────────────────────────────────────

NUM_RUNS = 10  # Same as Trushar!

PHASES = [
    'approaching_wall',
    'wall_following',
    'obstacle_detected',
    'obstacle_avoidance',
    'wall_reacquired',
    'wall_following_fail',
    # 'searching_wall',
]

PHASE_EXPECTED = {
    'approaching_wall':    'decreasing',
    'wall_following':      'constant',
    'obstacle_detected':   'decreasing',
    'obstacle_avoidance':  'increasing',
    'wall_reacquired':     'decreasing',
    'wall_following_fail': 'oscillating',
    'searching_wall':      'oscillating',
}

ALL_SENSORS = [
    'lidar_left',
    'lidar_right',
    'lidar_front',
    'lidar_front_right',
    # # 'imu_accel_x',
    # # 'imu_accel_y',
    # # 'imu_angular_z',
    # 'odom_linear_x',
]

DELTA_THRESHOLD = 0.01
# ──────────────────────────────────────────────────────────────


def load_csv_files():
    """Loads good run CSV files filtered by task!"""
    files = sorted([
        f for f in os.listdir(DATA_DIR)
        if f.endswith('.csv')])

    all_runs = []
    for filename in files:
        if 'good' not in filename:
            continue
        if TASK == 'pw' and \
                'pw' not in filename:
            continue
        if TASK == 'pill' and \
                'pill' not in filename:
            continue

        filepath = os.path.join(
            DATA_DIR, filename)
        try:
            df = pd.read_csv(filepath)
            # Remove idle phase!
            df = df[
                ~df['action_label'].isin(
                    ['idle', 'searching_wall'])
            ].reset_index(drop=True)
            run_id = filename.replace('.csv', '')
            all_runs.append({
                'run_id':   run_id,
                'filename': filename,
                'df':       df,
            })
        except Exception as e:
            print(f'ERROR: {filename}: {e}')

    print(f'Loaded {len(all_runs)} good run '
          f'CSV files for task={TASK}')
    return all_runs


def get_dominant_label(values, threshold):
    """Gets dominant label for a sensor."""
    inc = dec = con = 0
    for i in range(len(values) - 1):
        v1 = values[i]
        v2 = values[i+1]
        if pd.isna(v1) or pd.isna(v2):
            continue
        delta = float(v2) - float(v1)
        if delta > threshold:
            inc += 1
        elif delta < -threshold:
            dec += 1
        else:
            con += 1

    total = inc + dec + con
    if total == 0:
        return None
    if inc > 0 and dec > 0:
        minor = min(inc, dec)
        if minor / total > 0.2:
            return 'oscillating'
    if dec > inc and dec > con:
        return 'decreasing'
    elif inc > dec and inc > con:
        return 'increasing'
    else:
        return 'constant'


def get_pred_name(sensor, label):
    """Creates predicate name."""
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
    return f'{s}_{label}'


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
    lines.append('max_body(4).')
    lines.append('max_vars(1).')
    return '\n'.join(lines)


def run_popper(timeout=120):
    """Runs Popper once."""
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
            elif 'phase_correct' in line:
                rules.append(line.strip())

    if 'NO SOLUTION' in output:
        return None, {}
    return rules, scores


def prepare_popper_files(all_runs, phase):
    """
    Prepares bk.pl, exs.pl, bias.pl
    using dominant label per run per phase!
    Same data used for all 10 runs!
    """
    facts      = []
    pos_exs    = []
    neg_exs    = []
    predicates = set()

    for run in all_runs:
        run_id = run['run_id']
        df     = run['df']

        all_phases = df[
            'action_label'].unique()

        for current_phase in all_phases:
            phase_df = df[
                df['action_label'] ==
                current_phase
            ].reset_index(drop=True)

            if len(phase_df) < 2:
                continue

            state_id = (
                f'{run_id}_{current_phase}')

            any_fact = False
            for sensor in ALL_SENSORS:
                if sensor not in \
                        phase_df.columns:
                    continue
                values = phase_df[
                    sensor].values
                label = get_dominant_label(
                    values, DELTA_THRESHOLD)
                if label is None:
                    continue
                pred = get_pred_name(
                    sensor, label)
                predicates.add(pred)
                facts.append(
                    f'{pred}({state_id}).')
                any_fact = True

            if not any_fact:
                continue

            if current_phase == phase:
                pos_exs.append(
                    f'pos(phase_correct'
                    f'({state_id})).')
            else:
                neg_exs.append(
                    f'neg(phase_correct'
                    f'({state_id})).')

    return facts, pos_exs, neg_exs, predicates


def run_phase_10_times(all_runs, phase):
    """
    Runs Popper 10 times for one phase!
    Same as Trushar's approach!
    Collects all rules!
    Finds most consistent rule!
    """
    print(f'\nPreparing data for {phase}...')

    facts, pos_exs, neg_exs, predicates = \
        prepare_popper_files(all_runs, phase)

    print(f'pos={len(pos_exs)} '
          f'neg={len(neg_exs)}')

    if not pos_exs or not neg_exs:
        print('Not enough examples!')
        return None, {}

    # Write Popper files!
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

    # Run Popper NUM_RUNS times!
    all_rules = []
    all_scores = []

    for run_num in range(1, NUM_RUNS + 1):
        print(f'  Run {run_num}/{NUM_RUNS}...',
              end=' ')
        output = run_popper()
        rules, scores = extract_solution(output)

        # if rules:
        #     print(f'✅ {rules[0][:50]}')
        #     all_rules.extend(rules)
        if rules:
            print(f'✅ {rules[0][:60]}')
            for r in rules:
                head, body = r.split(':-')
                lits = sorted(
                    l.strip() for l in
                    body.strip().rstrip('.')
                    .split('),'))
                lits = [l if l.endswith(')')
                        else l + ')' for l in lits]
                all_rules.append(
                    f"{head.strip()}:- "
                    f"{','.join(lits)}.")        
            all_scores.append(scores)
        else:
            print('❌ NO SOLUTION')

    if not all_rules:
        return None, {}

    # Find most common rule!
    rule_counter = Counter(all_rules)
    most_common = rule_counter.most_common()

    return most_common, all_scores


def save_results(phase, most_common,
                 all_scores):
    """Saves results."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(
        RESULTS_DIR,
        f'{phase}_rules.txt')

    with open(path, 'w') as f:
        f.write(f'Phase: {phase}\n')
        f.write(f'Task: {TASK}\n')
        f.write('Method: RAW DOMINANT '
                '(10 runs)\n')
        f.write('Good runs only!\n')
        f.write('='*50 + '\n\n')

        if most_common:
            f.write('RULES (most common first):\n')
            for rule, count in most_common:
                f.write(
                    f'  [{count}/{NUM_RUNS}] '
                    f'{rule}\n')
            f.write('\n')
            if all_scores:
                avg_r = sum(
                    s.get('recall', 0)
                    for s in all_scores
                ) / len(all_scores)
                f.write(
                    f'Avg Recall: {avg_r:.2f}\n')
        else:
            f.write('NO SOLUTION\n')


def generate_summary(all_results):
    """Generates summary."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(
        RESULTS_DIR, 'summary.txt')

    with open(path, 'w') as f:
        f.write('ILP PHASE LEARNING SUMMARY\n')
        f.write(f'Task: {TASK}\n')
        f.write('Method: RAW DOMINANT '
                f'({NUM_RUNS} runs)\n')
        f.write('Good runs only!\n')
        f.write('='*60 + '\n\n')

        for phase, most_common, \
                all_scores in all_results:
            f.write(f'Phase: {phase}\n')
            f.write(
                f'Expected: '
                f'{PHASE_EXPECTED[phase]}\n')

            if most_common:
                f.write('Most consistent rule:\n')
                rule, count = most_common[0]
                f.write(
                    f'  [{count}/{NUM_RUNS}x] '
                    f'{rule}\n')
                f.write('\nAll rules found:\n')
                for r, c in most_common:
                    f.write(
                        f'  [{c}/{NUM_RUNS}x] '
                        f'{r}\n')
                if all_scores:
                    avg_r = sum(
                        s.get('recall', 0)
                        for s in all_scores
                    ) / len(all_scores)
                    f.write(
                        f'Avg Recall: '
                        f'{avg_r:.2f}\n')
            else:
                f.write('NO SOLUTION\n')
            f.write('\n')

    print(f'Summary: {path}')


# ── MAIN ──────────────────────────────────────────────────────
if __name__ == '__main__':

    print('='*60)
    print('ILP PHASE LEARNER - RAW DOMINANT')
    print(f'Task: {TASK}')
    print(f'Runs per phase: {NUM_RUNS}')
    print('Good runs only!')
    print('ALL sensors combined!')
    print('='*60)

    all_runs = load_csv_files()
    all_phase_results = []

    for phase in PHASES:
        print(f'\n{"#"*50}')
        print(f'# PHASE: {phase}')
        print(f'{"#"*50}')

        most_common, all_scores = \
            run_phase_10_times(
                all_runs, phase)

        if most_common:
            print(f'\n✅ Most consistent:')
            print(f'  {most_common[0]}')
        else:
            print('❌ NO SOLUTION')

        save_results(
            phase, most_common, all_scores)
        all_phase_results.append(
            (phase, most_common, all_scores))

    generate_summary(all_phase_results)

    print('\n' + '='*60)
    print('COMPLETE!')
    print(f'Results: {RESULTS_DIR}')
    print('='*60)