#!/usr/bin/env python3
"""
ILP Phase Learner - QTA (10 Runs)
=================================
Identical setup to ilp_raw_loocv.py:
- good runs only
- idle + searching_wall removed
- same 4 lidar sensors
- 10 Popper runs, same rule counting

ONLY difference: labels come from QTA shapes
(qta_results/*.json) instead of dominant
row-by-row deltas.

Change only TASK for each task.

Author: Alisha Syed Karimulla
"""

import os
import json
import subprocess
from collections import Counter

# ── CONFIGURATION ─────────────────────────────
QTA_DIR     = os.path.expanduser('~/rnd_ws/qta_results')
POPPER_DIR  = os.path.expanduser('~/rnd_ws/popper_run')
POPPER_PATH = os.path.expanduser('~/Popper/popper.py')
PYTHON_PATH = os.path.expanduser('~/popper_env/bin/python')

# ── CHANGE ONLY THIS FOR EACH TASK ────────────
# TASK = 'pw' 
# TASK = 'pill'  
TASK = 'all'
    # 'pw', 'pill' or 'all'
# ──────────────────────────────────────────────

RESULTS_DIR = os.path.expanduser({
    'pw':   '~/rnd_ws/ilp_results_qta_10runs_plain',
    'pill': '~/rnd_ws/ilp_results_qta_10runs_pillar',
    'all':  '~/rnd_ws/ilp_results_qta_10runs_combined',
}[TASK])

# Same 4 lidars as the RAW runs
ALL_SENSORS = [
    'lidar_left',
    'lidar_right',
    'lidar_front',
    'lidar_front_right',
]

EXCLUDED_PHASES = ['idle', 'searching_wall']

PHASES = [
    'approaching_wall',
    'wall_following',
    'obstacle_detected',
    'obstacle_avoidance',
    'wall_reacquired',
    'wall_following_fail',
]

NUM_RUNS = 10
# ──────────────────────────────────────────────


def load_qta_files():
    """Loads good-run QTA JSON files for TASK."""
    runs = []
    for fn in sorted(os.listdir(QTA_DIR)):
        if not fn.endswith('_qta.json'):
            continue
        if 'good' not in fn:
            continue
        if TASK == 'pw' and not fn.startswith('pw'):
            continue
        if TASK == 'pill' and not fn.startswith('pill'):
            continue
        with open(os.path.join(QTA_DIR, fn)) as f:
            runs.append(json.load(f))
    print(f'Loaded {len(runs)} good-run QTA files '
          f'for task={TASK}')
    return runs


def pred_name(sensor, shape):
    s = {
        'lidar_left':        'lidar',
        'lidar_right':       'lidar_r',
        'lidar_front':       'lidar_f',
        'lidar_front_right': 'lidar_fr',
    }.get(sensor, sensor)
    sh = shape.replace('is_', '')
    return f'{s}_{sh}'


def prepare(runs, phase):
    """One state per run+phase, QTA shape per sensor.
    pos = target phase, neg = every other phase."""
    facts, pos, neg, preds = [], [], [], set()
    for run in runs:
        run_id  = run['run_id']
        windows = run.get('windows', {})
        for cur, data in windows.items():
            if cur in EXCLUDED_PHASES:
                continue
            sid = f'{run_id}_{cur}'
            any_fact = False
            for sensor in ALL_SENSORS:
                shape = data.get(sensor, {}).get('shape')
                if not shape:
                    continue
                p = pred_name(sensor, shape)
                preds.add(p)
                facts.append(f'{p}({sid}).')
                any_fact = True
            if not any_fact:
                continue
            if cur == phase:
                pos.append(f'pos(phase_correct({sid})).')
            else:
                neg.append(f'neg(phase_correct({sid})).')
    return facts, pos, neg, preds


def bias(preds):
    L = ['head_pred(phase_correct,1).']
    L += [f'body_pred({p},1).' for p in sorted(preds)]
    L += ['type(phase_correct,(run,)).']
    L += [f'type({p},(run,)).' for p in sorted(preds)]
    L += ['direction(phase_correct,(in,)).']
    L += [f'direction({p},(in,)).' for p in sorted(preds)]
    L += ['max_clauses(3).', 'max_body(4).',
          'max_vars(1).']
    return '\n'.join(L)


def run_popper(timeout=120):
    r = subprocess.run(
        [PYTHON_PATH, POPPER_PATH, POPPER_DIR,
         '--stats', '--timeout', str(timeout)],
        capture_output=True, text=True)
    return r.stdout + r.stderr


def extract(output):
    rules, scores, in_sol = [], {}, False
    for line in output.split('\n'):
        if '** SOLUTION **' in line:
            in_sol = True
            continue
        if in_sol and '****' in line:
            in_sol = False
            continue
        if in_sol and line.strip():
            if 'Precision' in line:
                for t in line.split():
                    if t.startswith('Precision:'):
                        scores['precision'] = float(t.split(':')[1])
                    if t.startswith('Recall:'):
                        scores['recall'] = float(t.split(':')[1])
            elif 'phase_correct' in line:
                rules.append(line.strip())
    if 'NO SOLUTION' in output:
        return None, {}
    return rules, scores


def normalise(rule):
    """Sort body literals so A,B == B,A."""
    head, body = rule.split(':-')
    lits = sorted(l.strip() for l in
                  body.strip().rstrip('.').split('),'))
    lits = [l if l.endswith(')') else l + ')' for l in lits]
    return f"{head.strip()}:- {','.join(lits)}."


def run_phase(runs, phase):
    facts, pos, neg, preds = prepare(runs, phase)
    print(f'pos={len(pos)} neg={len(neg)}')
    if not pos or not neg:
        print('Not enough examples!')
        return None, []

    os.makedirs(POPPER_DIR, exist_ok=True)
    with open(os.path.join(POPPER_DIR, 'bk.pl'), 'w') as f:
        f.write('\n'.join(facts))
    with open(os.path.join(POPPER_DIR, 'exs.pl'), 'w') as f:
        f.write('% Positive\n' + '\n'.join(pos) +
                '\n\n% Negative\n' + '\n'.join(neg))
    with open(os.path.join(POPPER_DIR, 'bias.pl'), 'w') as f:
        f.write(bias(preds))

    all_rules, all_scores = [], []
    for i in range(1, NUM_RUNS + 1):
        print(f'  Run {i}/{NUM_RUNS}...', end=' ')
        rules, scores = extract(run_popper())
        if rules:
            print(f'✅ {rules[0][:60]}')
            all_rules += [normalise(r) for r in rules]
            # all_rules.append('  OR  '.join(
            #     sorted(normalise(r) for r in rules)))
            all_scores.append(scores)
        else:
            print('❌ NO SOLUTION')
    if not all_rules:
        return None, []
    return Counter(all_rules).most_common(), all_scores


def write_summary(results):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, 'summary.txt')
    with open(path, 'w') as f:
        f.write('ILP PHASE LEARNING SUMMARY\n')
        f.write(f'Task: {TASK}\n')
        f.write(f'Method: QTA ({NUM_RUNS} runs)\n')
        f.write(f'Sensors: {", ".join(ALL_SENSORS)}\n')
        f.write('Good runs only! idle + searching_wall removed\n')
        f.write('=' * 60 + '\n\n')
        for phase, common, scores in results:
            f.write(f'Phase: {phase}\n')
            if common:
                f.write('All rules found:\n')
                for r, c in common:
                    f.write(f'  [{c}/{NUM_RUNS}x] {r}\n')
                avg = sum(s.get('recall', 0) for s in scores) / len(scores)
                f.write(f'Avg Recall: {avg:.2f}\n')
            else:
                f.write('NO SOLUTION\n')
            f.write('\n')
    print(f'Summary: {path}')


if __name__ == '__main__':
    print('=' * 60)
    print(f'ILP PHASE LEARNER - QTA | Task: {TASK}')
    print(f'Sensors: {ALL_SENSORS}')
    print('=' * 60)
    runs = load_qta_files()
    results = []
    for phase in PHASES:
        print(f'\n# PHASE: {phase}')
        common, scores = run_phase(runs, phase)
        results.append((phase, common, scores))
    write_summary(results)