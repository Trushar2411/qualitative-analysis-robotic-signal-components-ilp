#!/usr/bin/env python3
"""
loo_entry.py  -  LEAVE-ONE-RUN-OUT test for the ENTRY experiment (RAW and QTA)

For every good run R of a task:
  1. learn one rule per phase with Popper on ALL OTHER good runs
     (same facts as ilp_*_entry.py: trend word + entry word per lidar,
      one example per phase occurrence, strict mode, same bias)
  2. apply that rule to the phase occurrences of the LEFT-OUT run R
     - held-out recall : rule matches the occurrences of its own phase
     - false alarms    : rule matches occurrences of OTHER phases
Nothing in your existing scripts or results is changed.

HOW TO RUN
  cd ~/rnd_ws/src/robile_wall_follower/signal_processing
  python3 loo_entry.py                    # all three tasks (takes a few minutes)
  TASKS=pill python3 loo_entry.py         # only the pillar task
OUTPUT
  printed tables + loo_results/loo_folds.csv, loo_results/loo_summary.csv
"""
import os, glob, re, shutil, subprocess, tempfile
import pandas as pd
import entry_features as EF

PYTHON_PATH = os.path.expanduser('~/popper_env/bin/python')
POPPER_PATH = os.path.expanduser('~/Popper/popper.py')
TIMEOUT     = 120
OUT_DIR     = 'loo_results'
TASKS       = os.environ.get('TASKS', 'pw pill all').split()
PHASES      = ['approaching_wall', 'wall_following', 'obstacle_detected',
               'obstacle_avoidance', 'wall_reacquired']
PREFIX      = {'lidar_left': 'lidar', 'lidar_right': 'lidar_r',
               'lidar_front': 'lidar_f', 'lidar_front_right': 'lidar_fr'}


def raw_label(values, threshold=0.01):          # same as ilp_raw_loocv.py
    inc = dec = con = 0
    for i in range(len(values) - 1):
        v1, v2 = values[i], values[i + 1]
        if pd.isna(v1) or pd.isna(v2):
            continue
        d = float(v2) - float(v1)
        if d > threshold:
            inc += 1
        elif d < -threshold:
            dec += 1
        else:
            con += 1
    total = inc + dec + con
    if total == 0:
        return None
    if inc > 0 and dec > 0 and min(inc, dec) / total > 0.2:
        return 'oscillating'
    if dec > inc and dec > con:
        return 'decreasing'
    if inc > dec and inc > con:
        return 'increasing'
    return 'constant'


def occurrences(run, method):
    """list of (example_id, phase, set_of_predicate_names) for one run"""
    f = EF.find_csv(run)
    out = []
    for s in EF.segments(pd.read_csv(f)):
        seg = s['seg'].reset_index(drop=True)
        if len(seg) < 2 or s['phase'] not in PHASES:
            continue
        preds = set()
        for sensor, pre in PREFIX.items():
            if sensor not in seg.columns:
                continue
            w = raw_label(seg[sensor].values) if method == 'RAW' else \
                EF.apply_qta(seg[sensor].values).replace('is_', '')
            if w:
                preds.add(f'{pre}_{w}')
            e = EF.entry_label(seg, s['prev'], sensor)
            if e:
                preds.add(f'{pre}_{e}')
        if preds:
            out.append((f"{run}_{s['phase']}_{s['k']}", s['phase'], preds))
    return out


def write_task(folder, train_occ, phase):
    facts, pos, neg, names = [], [], [], set()
    for ex, ph, preds in train_occ:
        for p in sorted(preds):
            facts.append(f'{p}({ex}).')
            names.add(p)
        (pos if ph == phase else neg).append(f'{"pos" if ph == phase else "neg"}(phase_correct({ex})).')
    bias = ['head_pred(phase_correct,1).']
    bias += [f'body_pred({p},1).' for p in sorted(names)]
    bias += ['type(phase_correct,(run,)).'] + [f'type({p},(run,)).' for p in sorted(names)]
    bias += ['direction(phase_correct,(in,)).'] + [f'direction({p},(in,)).' for p in sorted(names)]
    bias += ['max_clauses(3).', 'max_body(4).', 'max_vars(1).']
    open(os.path.join(folder, 'bk.pl'), 'w').write('\n'.join(facts) + '\n')
    open(os.path.join(folder, 'exs.pl'), 'w').write('\n'.join(pos + neg) + '\n')
    open(os.path.join(folder, 'bias.pl'), 'w').write('\n'.join(bias) + '\n')
    return len(pos)


def run_popper(folder):
    try:
        r = subprocess.run([PYTHON_PATH, POPPER_PATH, folder], capture_output=True, text=True, timeout=TIMEOUT)
        return r.stdout if 'SOLUTION' in r.stdout else r.stdout + '\n' + r.stderr
    except subprocess.TimeoutExpired:
        return 'TIMEOUT'


def parse_rule(output):
    """only the clauses inside the LAST '*** SOLUTION ***' block; [] = no solution"""
    if output == 'TIMEOUT':
        return []
    lines = output.splitlines()
    starts = [i for i, l in enumerate(lines) if 'SOLUTION' in l and l.strip().startswith('*') and 'NO SOLUTION' not in l]
    if not starts:
        return []
    clauses = []
    for l in lines[starts[-1] + 1:]:
        if l.strip().startswith('*'):
            break
        if ':-' in l and 'phase_correct' in l:
            c = re.findall(r'([a-z_]+)\(V0\)', l.split(':-', 1)[1])
            if c and c not in clauses:
                clauses.append(c)
    return clauses


def matches(clauses, preds):
    return any(all(b in preds for b in c) for c in clauses)


def runs_for(task):
    good = sorted({'_'.join(os.path.basename(f).split('_')[:3])
                   for f in glob.glob(os.path.join(EF.CLEANED_DIR, '*_good_*.csv'))})
    if task == 'pw':
        return [r for r in good if r.startswith('pw_')]
    if task == 'pill':
        return [r for r in good if r.startswith('pill_')]
    return good


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = []
    for task in TASKS:
        runs = runs_for(task)
        for method in ['RAW', 'QTA']:
            occ = {r: occurrences(r, method) for r in runs}
            for held in runs:
                train = [o for r in runs if r != held for o in occ[r]]
                test = occ[held]
                for phase in PHASES:
                    if not any(ph == phase for _, ph, _ in test):
                        continue
                    tmp = tempfile.mkdtemp(prefix='loo_')
                    n_pos = write_task(tmp, train, phase)
                    raw_out = run_popper(tmp) if n_pos else 'NO SOLUTION'
                    if not os.path.exists(os.path.join(OUT_DIR, 'first_popper_output.txt')):
                        open(os.path.join(OUT_DIR, 'first_popper_output.txt'), 'w').write(raw_out)
                    rule = parse_rule(raw_out)
                    shutil.rmtree(tmp, ignore_errors=True)
                    for ex, ph, preds in test:
                        rows.append(dict(task=task, method=method, held_out=held, phase=phase,
                                         example=ex, is_target=(ph == phase),
                                         matched=matches(rule, preds),
                                         rule=' OR '.join('+'.join(c) for c in rule) or 'NO SOLUTION'))
                    print(f'{task:4} {method} held-out {held:13} {phase:19} '
                          f'rule: {" OR ".join("+".join(c) for c in rule) or "NO SOLUTION"}')
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT_DIR, 'loo_folds.csv'), index=False)

    pos = t[t.is_target].groupby(['task', 'phase', 'method'])['matched'].agg(['sum', 'count'])
    neg = t[~t.is_target].groupby(['task', 'phase', 'method'])['matched'].agg(['sum', 'count'])
    summ = pd.DataFrame({
        'heldout_recall': (pos['sum'] / pos['count']).round(2),
        'recognised': pos['sum'].astype(int).astype(str) + '/' + pos['count'].astype(str),
        'false_alarms': neg['sum'].astype(int).astype(str) + '/' + neg['count'].astype(str),
    }).reset_index()
    summ.to_csv(os.path.join(OUT_DIR, 'loo_summary.csv'), index=False)
    pd.set_option('display.width', 200)
    for task in TASKS:
        s = summ[summ.task == task]
        print(f'\n=== LEAVE-ONE-RUN-OUT · task={task} ===')
        print(s.pivot(index='phase', columns='method', values=['recognised', 'false_alarms'])
               .reindex([p for p in PHASES if p in set(s.phase)]).to_string())
        avg = s.groupby('method')['heldout_recall'].mean().round(2)
        print('average held-out recall: ' + '  '.join(f'{m} {v}' for m, v in avg.items()))
    print(f'\nSaved: {OUT_DIR}/loo_folds.csv and {OUT_DIR}/loo_summary.csv')


if __name__ == '__main__':
    main()