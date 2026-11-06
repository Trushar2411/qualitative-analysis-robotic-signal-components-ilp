#!/usr/bin/env python3
"""
count_rule.py  -  which part of each learned rule fits each phase piece? (17 good runs)

Uses the SAME words as the ILP experiment:
  trend word per lidar (RAW = row-to-row count, QTA = straight-line fit)
  + jump word at the phase start (5 rows after - 5 rows before, 10 cm)
Rules = the combined-task rules with jump words (slide 18).

HOW TO RUN (signal_processing folder, next to entry_features.py)
  PHASE=wall_following     ~/popper_env/bin/python count_rule.py
  PHASE=approaching_wall   ~/popper_env/bin/python count_rule.py
  PHASE=obstacle_detected  ~/popper_env/bin/python count_rule.py
  PHASE=obstacle_avoidance ~/popper_env/bin/python count_rule.py
  PHASE=wall_reacquired    ~/popper_env/bin/python count_rule.py
Saved to ~/rnd_ws/phase_plots/rule_check_<phase>.csv
"""
import os, glob
import pandas as pd
import entry_features as EF

PHASE = os.environ.get('PHASE', 'wall_following')
SHORT = {'lidar_left': 'L', 'lidar_right': 'R', 'lidar_front': 'F', 'lidar_front_right': 'FR'}
ABBR = {'increasing': 'inc', 'decreasing': 'dec', 'constant': 'const', 'oscillating': 'osc',
        'zero': 'zero', 'jump_up': 'jump_up', 'jump_down': 'jump_down', 'no_jump': 'no_jump'}

# rules with jump words, combined task: list of parts; each part = list of (lidar, word) that must ALL be true
RULES = {
    'approaching_wall':   {'RAW': [[('L', 'dec')]],
                           'QTA': [[('L', 'dec')], [('FR', 'dec'), ('FR', 'jump_down')]]},
    'wall_following':     {'RAW': [[('L', 'no_jump'), ('R', 'const')], [('L', 'const'), ('R', 'jump_up')]],
                           'QTA': [[('FR', 'osc')], [('L', 'const'), ('FR', 'const'), ('L', 'no_jump')]]},
    'obstacle_detected':  {'RAW': [[('L', 'jump_down'), ('R', 'no_jump')], [('L', 'const'), ('R', 'jump_down')]],
                           'QTA': [[('L', 'jump_down'), ('FR', 'const'), ('FR', 'no_jump')]]},
    'obstacle_avoidance': {'RAW': [[('L', 'inc')]],
                           'QTA': [[('L', 'inc'), ('FR', 'no_jump')]]},
    'wall_reacquired':    {'RAW': [[('L', 'jump_up')]],
                           'QTA': [[('L', 'jump_up')]]},
}


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


def words(seg, prev, method):
    w = {}
    for sensor, s in SHORT.items():
        if sensor not in seg.columns:
            continue
        t = raw_label(seg[sensor].values) if method == 'RAW' else EF.apply_qta(seg[sensor].values).replace('is_', '')
        w[s] = {ABBR.get(t, t)} if t else set()
        e = EF.entry_label(seg, prev, sensor)
        if e:
            w[s].add(ABBR[e])
    return w


def fits(part, w):
    return all(word in w.get(s, set()) for s, word in part)


rows = []
for f in sorted(glob.glob(os.path.join(EF.CLEANED_DIR, '*_good_*.csv'))):
    run = '_'.join(os.path.basename(f).split('_')[:3])
    for s in EF.segments(pd.read_csv(f)):
        seg = s['seg'].reset_index(drop=True)
        if len(seg) < 2:
            continue
        row = dict(run=run, phase=s['phase'], piece=s['k'], rows=len(seg))
        for m in ['RAW', 'QTA']:
            w = words(seg, s['prev'], m)
            for s_ in ['L', 'R', 'FR']:
                row[f'{m}_{s_}'] = '+'.join(sorted(w.get(s_, set()))) or '-'
            parts = [i + 1 for i, p in enumerate(RULES[PHASE][m]) if fits(p, w)]
            row[f'{m}_fits'] = ' & '.join(f'part {p}' for p in parts) or 'NONE'
        rows.append(row)

t = pd.DataFrame(rows)
own = t[t.phase == PHASE]
other = t[t.phase != PHASE]
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
for m in ['RAW', 'QTA']:
    print(f'\n================  {m} rule for {PHASE}  ================')
    print(own[['run', 'piece', 'rows', f'{m}_L', f'{m}_R', f'{m}_FR', f'{m}_fits']].to_string(index=False))
    print(f'\n{m}: {len(own)} {PHASE} pieces')
    print(own[f'{m}_fits'].value_counts().to_string())
    wrong = other[other[f'{m}_fits'] != 'NONE']
    print(f'{m}: rule also fires on {len(wrong)} of {len(other)} pieces of OTHER phases (should be 0 in strict mode)')
    if len(wrong):
        print(wrong[['run', 'phase', 'piece', f'{m}_fits']].to_string(index=False))
out = os.path.expanduser(f'~/rnd_ws/phase_plots/rule_check_{PHASE}.csv')
os.makedirs(os.path.dirname(out), exist_ok=True)
own.to_csv(out, index=False)
print('\nSaved', out)
