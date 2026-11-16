#!/usr/bin/env python3
"""
ilp_multisensor.py  -  jump-word rules with LIDAR ONLY vs LIDAR + ODOMETRY (pillar task)

Signals
  lidar      : lidar_left, lidar_right, lidar_front, lidar_front_right   (exactly as before)
  odometry   : side_speed      (+ = moving left/toward the wall, - = right)   from add_odometry.py
               turn_rate_odom  (how fast the robot twists)                      from add_odometry.py
Words per phase piece (same idea as before)
  trend word : RAW (row-to-row count) or QTA (one straight line)
  jump word  : mean of first 5 rows - mean of last 5 rows of the previous phase
  Lidar words are computed EXACTLY as in ilp_*_entry.py.
  Speeds cross zero, so the lidar's "percent of the mean" limits do not work for them. Instead the
  same percentages are taken of the signal's typical range (scale = 95th - 5th percentile over all runs):
     RAW step  1 % of scale   (lidar: 1 cm)        jump 10 % of scale  (lidar: 10 cm)
     QTA constant if spread < 5 % of scale, increasing/decreasing if slope > 0.5 % of scale per row,
         oscillating if spread > 15 % of scale      (same numbers as QTA for the lidar)
For each sensor set and method:
  1. learn one rule per phase on ALL good pillar runs (strict mode, same bias as before)
  2. leave-one-run-out: learn on 6 runs, test on the 7th (recognised + false alarms)

  3. NEW ENVIRONMENT: the rules learned on the pillar runs are applied unchanged to the 10 plain-wall runs

HOW TO RUN (pipeline folder, after add_odometry.py); -u prints each line immediately
  ~/popper_env/bin/python -u ilp_multisensor.py                                  # strict Popper (default)
  POPPER_ARGS=--noisy ~/popper_env/bin/python -u ilp_multisensor.py              # noisy Popper
  MAX_CLAUSES=1 ~/popper_env/bin/python -u ilp_multisensor.py                    # only one AND-rule per phase
  SETS=lidar+odom ~/popper_env/bin/python -u ilp_multisensor.py                  # one sensor set only
Each setting writes to its own folder, e.g. multisensor_results/strict_c3_b4/
OUTPUT
  multisensor_results/<setting>/rules_all_runs.csv, loo_folds.csv, loo_summary.csv, new_environment_plain_wall.csv
"""
import os, glob, re, shutil, subprocess, tempfile
import numpy as np
import pandas as pd
import entry_features as EF

PYTHON_PATH = os.path.expanduser('~/popper_env/bin/python')
POPPER_PATH = os.path.expanduser('~/Popper/popper.py')
DATA_DIR    = os.path.expanduser('~/rnd_ws/data_cleaned_odom')
OUT_DIR     = 'multisensor_results'
TIMEOUT     = 180
SETS        = os.environ.get('SETS', 'lidar lidar+odom').split()
POPPER_ARGS = os.environ.get('POPPER_ARGS', '').split()          # e.g. "--noisy"
MAX_CLAUSES = int(os.environ.get('MAX_CLAUSES', 3))
MAX_BODY    = int(os.environ.get('MAX_BODY', 4))
TAG         = ('noisy' if '--noisy' in POPPER_ARGS else 'strict') + f'_c{MAX_CLAUSES}_b{MAX_BODY}'
OUT_DIR     = os.path.join(OUT_DIR, TAG + ('' if SETS == ['lidar', 'lidar+odom'] else '_' + '_'.join(SETS)))
PHASES      = ['approaching_wall', 'wall_following', 'obstacle_detected', 'obstacle_avoidance', 'wall_reacquired']
LIDAR       = {'lidar_left': 'lidar', 'lidar_right': 'lidar_r', 'lidar_front': 'lidar_f', 'lidar_front_right': 'lidar_fr'}
ODOM        = {'side_speed': 'side', 'turn_rate_odom': 'turn', 'total_speed': 'speed'}
SET_ODOM    = {'lidar': [], 'lidar+odom': ['side_speed', 'turn_rate_odom'],
               'lidar+side': ['side_speed'], 'lidar+turn': ['turn_rate_odom'],
               'lidar+speed': ['total_speed'], 'lidar+side+speed': ['side_speed', 'total_speed']}


def raw_label(values, threshold):                  # same logic as ilp_raw_loocv.py
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


def qta_scaled(values, scale):                     # QTA, limits relative to the signal's range
    v = np.array(values, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) < 3:
        return None
    sd = np.std(v)
    if sd < 0.05 * scale:
        return 'constant'
    slope = np.polyfit(np.arange(len(v)), v, 1)[0] / scale
    if slope > 0.005:
        return 'increasing'
    if slope < -0.005:
        return 'decreasing'
    return 'oscillating' if sd > 0.15 * scale else 'constant'


def jump_scaled(seg, prev, col, scale):
    if prev is None or col not in prev.columns:
        return None
    a = np.nanmean(seg[col].values[:EF.N_EDGE].astype(float))
    b = np.nanmean(prev[col].values[-EF.N_EDGE:].astype(float))
    if np.isnan(a) or np.isnan(b):
        return None
    j = a - b
    return 'jump_up' if j > 0.10 * scale else 'jump_down' if j < -0.10 * scale else 'no_jump'


def load_runs(pattern='pill_good_*.csv'):
    runs = {}
    for f in sorted(glob.glob(os.path.join(DATA_DIR, pattern))):
        runs['_'.join(os.path.basename(f).split('_')[:3])] = pd.read_csv(f)
    return runs


def scales(runs):
    allv = pd.concat(runs.values(), ignore_index=True)
    return {c: float(np.nanpercentile(allv[c], 95) - np.nanpercentile(allv[c], 5)) for c in ODOM if c in allv}


def occurrences(df, run, method, odom_cols, sc):
    out = []
    for s in EF.segments(df):
        seg = s['seg'].reset_index(drop=True)
        if len(seg) < 2 or s['phase'] not in PHASES:
            continue
        preds = set()
        for col, pre in LIDAR.items():                                   # exactly as ilp_*_entry.py
            if col not in seg.columns:
                continue
            w = raw_label(seg[col].values, 0.01) if method == 'RAW' else EF.apply_qta(seg[col].values).replace('is_', '')
            if w:
                preds.add(f'{pre}_{w}')
            e = EF.entry_label(seg, s['prev'], col)
            if e:
                preds.add(f'{pre}_{e}')
        if odom_cols:
            for col, pre in ODOM.items():
                if col not in odom_cols or col not in seg.columns or col not in sc:
                    continue
                w = raw_label(seg[col].values, 0.01 * sc[col]) if method == 'RAW' else qta_scaled(seg[col].values, sc[col])
                if w:
                    preds.add(f'{pre}_{w}')
                e = jump_scaled(seg, s['prev'], col, sc[col])
                if e:
                    preds.add(f'{pre}_{e}')
        if preds:
            out.append((f"{run}_{s['phase']}_{s['k']}", s['phase'], preds))
    return out


def write_task(folder, train, phase):
    facts, pos, neg, names = [], [], [], set()
    for ex, ph, preds in train:
        for p in sorted(preds):
            facts.append(f'{p}({ex}).')
            names.add(p)
        (pos if ph == phase else neg).append(f'{"pos" if ph == phase else "neg"}(phase_correct({ex})).')
    bias = ['head_pred(phase_correct,1).'] + [f'body_pred({p},1).' for p in sorted(names)]
    bias += ['type(phase_correct,(run,)).'] + [f'type({p},(run,)).' for p in sorted(names)]
    bias += ['direction(phase_correct,(in,)).'] + [f'direction({p},(in,)).' for p in sorted(names)]
    bias += [f'max_clauses({MAX_CLAUSES}).', f'max_body({MAX_BODY}).', 'max_vars(1).']
    open(os.path.join(folder, 'bk.pl'), 'w').write('\n'.join(facts) + '\n')
    open(os.path.join(folder, 'exs.pl'), 'w').write('\n'.join(pos + neg) + '\n')
    open(os.path.join(folder, 'bias.pl'), 'w').write('\n'.join(bias) + '\n')
    return len(pos)


def run_popper(folder):
    try:
        r = subprocess.run([PYTHON_PATH, POPPER_PATH, folder] + POPPER_ARGS, capture_output=True, text=True, timeout=TIMEOUT)
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


def learn(train, phase):
    tmp = tempfile.mkdtemp(prefix='multi_')
    n = write_task(tmp, train, phase)
    out = run_popper(tmp) if n else 'NO SOLUTION'
    shutil.rmtree(tmp, ignore_errors=True)
    return parse_rule(out), out == 'TIMEOUT'


def show(rule):
    short = lambda p: (p.replace('lidar_fr_', 'FR ').replace('lidar_f_', 'F ').replace('lidar_r_', 'R ')
                        .replace('lidar_', 'L ').replace('side_', 'SIDE ').replace('turn_', 'TURN ').replace('speed_', 'SPEED ')
                        .replace('increasing', 'inc').replace('decreasing', 'dec').replace('constant', 'const')
                        .replace('oscillating', 'osc').replace('jump_up', 'jump↑').replace('jump_down', 'jump↓')
                        .replace('no_jump', 'no jump'))
    return ' OR '.join('(' + ' + '.join(short(p) for p in c) + ')' if len(rule) > 1 else ' + '.join(short(p) for p in c)
                       for c in rule) or 'NO SOLUTION'


def matches(rule, preds):
    return any(all(b in preds for b in c) for c in rule)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    runs = load_runs()
    sc = scales(runs)
    plain = load_runs('pw_good_*.csv')
    print(f'settings: Popper {" ".join(POPPER_ARGS) or "strict (default)"}, max_clauses {MAX_CLAUSES}, max_body {MAX_BODY}  -> {OUT_DIR}/')
    print(f'{len(runs)} pillar runs (learn) + {len(plain)} plain-wall runs (new-environment test) from {DATA_DIR}')
    print('odometry scales (95th-5th percentile): ' + ', '.join(f'{k} {v:.3f}' for k, v in sc.items()))
    print('  -> jump limits: ' + ', '.join(f'{k} {0.1 * v:.3f}' for k, v in sc.items()) + '\n')
    rules, folds, envtest = [], [], []
    for sset in SETS:
        use_odom = SET_ODOM[sset]
        for method in ['RAW', 'QTA']:
            occ = {r: occurrences(df, r, method, use_odom, sc) for r, df in runs.items()}
            allocc = [o for r in runs for o in occ[r]]
            plainocc = [o for r, df in plain.items() for o in occurrences(df, r, method, use_odom, sc)]
            print(f'===== {sset} · {method} · rules learned on all {len(runs)} runs =====')
            for phase in PHASES:
                rule, to = learn(allocc, phase)
                pos = [p for ex, ph, p in allocc if ph == phase]
                neg = [p for ex, ph, p in allocc if ph != phase]
                rec = np.mean([matches(rule, p) for p in pos]) if pos else np.nan
                fa = sum(matches(rule, p) for p in neg)
                uses = sorted({p.split('_')[0] if not p.startswith('lidar') else 'lidar' for c in rule for p in c})
                rules.append(dict(set=sset, method=method, phase=phase, rule=show(rule), recall=round(rec, 2),
                                  wrong_fires=fa, uses_odometry=any(u in ('side', 'turn') for u in uses), timeout=to))
                print(f'  {phase:19} {show(rule)}   · recall {rec:.2f}' + ('  [TIMEOUT]' if to else ''))
                for ex, ph, p in plainocc:                                   # rules learned on pillar runs, tested on plain wall
                    envtest.append(dict(set=sset, method=method, phase=phase, is_target=ph == phase, matched=matches(rule, p)))
            for held in runs:
                train = [o for r in runs if r != held for o in occ[r]]
                for phase in PHASES:
                    if not any(ph == phase for _, ph, _ in occ[held]):
                        continue
                    rule, _ = learn(train, phase)
                    for ex, ph, preds in occ[held]:
                        folds.append(dict(set=sset, method=method, held_out=held, phase=phase,
                                          is_target=ph == phase, matched=matches(rule, preds)))
            print(f'  (leave-one-run-out done for {sset} · {method})\n')
    pd.DataFrame(rules).to_csv(os.path.join(OUT_DIR, 'rules_all_runs.csv'), index=False)
    t = pd.DataFrame(folds)
    t.to_csv(os.path.join(OUT_DIR, 'loo_folds.csv'), index=False)

    pos = t[t.is_target].groupby(['set', 'method'])['matched'].agg(['sum', 'count'])
    neg = t[~t.is_target].groupby(['set', 'method'])['matched'].agg(['sum', 'count'])
    summ = pd.DataFrame({'recognised': pos['sum'].astype(int).astype(str) + '/' + pos['count'].astype(str),
                         'false_alarms': neg['sum'].astype(int).astype(str) + '/' + neg['count'].astype(str)})
    r = pd.DataFrame(rules)
    summ['phases_using_odometry'] = r.groupby(['set', 'method'])['uses_odometry'].sum().astype(int).astype(str) + '/5'
    summ.to_csv(os.path.join(OUT_DIR, 'loo_summary.csv'))
    print('===== LEAVE-ONE-RUN-OUT (pillar task): lidar only vs lidar + odometry =====')
    print(summ.to_string())
    e = pd.DataFrame(envtest)
    if len(e):
        ep = e[e.is_target].groupby(['set', 'method', 'phase'])['matched'].agg(['sum', 'count'])
        en = e[~e.is_target].groupby(['set', 'method'])['matched'].agg(['sum', 'count'])
        env = (ep['sum'].astype(int).astype(str) + '/' + ep['count'].astype(str)).unstack('phase')
        env['false_alarms'] = en['sum'].astype(int).astype(str) + '/' + en['count'].astype(str)
        env.to_csv(os.path.join(OUT_DIR, 'new_environment_plain_wall.csv'))
        print('\n===== NEW ENVIRONMENT: rules learned on pillar runs, tested on the 10 plain-wall runs =====')
        print('(plain wall has only approaching_wall and wall_following; false alarms = pillar-phase rules firing there)')
        print(env.to_string())
    print(f'\nSaved in {OUT_DIR}/: rules_all_runs.csv, loo_folds.csv, loo_summary.csv, new_environment_plain_wall.csv')


if __name__ == '__main__':
    main()