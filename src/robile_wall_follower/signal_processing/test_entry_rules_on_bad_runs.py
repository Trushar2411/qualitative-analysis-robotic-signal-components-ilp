#!/usr/bin/env python3
"""
test_entry_rules_on_bad_runs.py  -  apply the ENTRY-experiment rules (combined task)
to good and bad runs. NOTHING is learned. For every phase occurrence: does the rule
of that phase match?

  good runs -> should match (training recall, sanity check)
  bad runs  -> a 'no' means the rule notices that this phase looked different

Labels are made exactly like in ilp_raw_entry.py / ilp_qta_entry.py
(entry_features.py: segments, entry jump, apply_qta; RAW dominant change).
pill_bad_02 is left out (lidar data mostly invalid).

HOW TO RUN
  cd ~/rnd_ws/src/robile_wall_follower/signal_processing
  python3 test_entry_rules_on_bad_runs.py
"""
import os, glob
import pandas as pd
import entry_features as EF

SKIP = ['pill_bad_02']
L, R, F, FR = 'lidar_left', 'lidar_right', 'lidar_front', 'lidar_front_right'
DETAIL_RUN = 'pill_bad_01'

# Rules learned on the COMBINED task (ilp_results_*_entry_combined/summary.txt)
# rule = list of clauses (OR); clause = list of (sensor, word) (AND)
RULES = {
    'RAW': {
        'approaching_wall':   [[(L, 'decreasing')]],
        'wall_following':     [[(L, 'no_jump'), (R, 'constant')], [(L, 'constant'), (R, 'jump_up')]],
        'obstacle_detected':  [[(L, 'jump_down'), (R, 'no_jump')], [(L, 'constant'), (R, 'jump_down')]],
        'obstacle_avoidance': [[(L, 'increasing')]],
        'wall_reacquired':    [[(L, 'jump_up')]],
    },
    'QTA': {
        'approaching_wall':   [[(L, 'decreasing')], [(FR, 'decreasing'), (FR, 'jump_down')]],
        'wall_following':     [[(FR, 'oscillating')], [(L, 'constant'), (FR, 'constant'), (L, 'no_jump')]],
        'obstacle_detected':  [[(FR, 'constant'), (FR, 'no_jump'), (L, 'jump_down')]],
        'obstacle_avoidance': [[(FR, 'no_jump'), (L, 'increasing')]],
        'wall_reacquired':    [[(L, 'jump_up')]],
    },
}


def raw_label(values, threshold=0.01):
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


def words(method, seg, prev):
    """set of (sensor, word) facts for one phase occurrence"""
    out = set()
    for s in [L, R, F, FR]:
        if s not in seg.columns:
            continue
        t = raw_label(seg[s].values) if method == 'RAW' else EF.apply_qta(seg[s].values).replace('is_', '')
        if t:
            out.add((s, t))
        e = EF.entry_label(seg, prev, s)
        if e:
            out.add((s, e))
    return out


def fires(rule, facts):
    return any(all(c in facts for c in clause) for clause in rule)


def short(facts):
    m = {L: 'left', R: 'right', F: 'front', FR: 'fr'}
    order = {L: 0, R: 1, F: 2, FR: 3}
    return ', '.join(f'{m[s]}={w}' for s, w in sorted(facts, key=lambda x: (order[x[0]], x[1])))


rows = []
for f in sorted(glob.glob(os.path.join(EF.CLEANED_DIR, '*.csv'))):
    run = '_'.join(os.path.basename(f).split('_')[:3])
    if run in SKIP:
        continue
    quality = 'good' if '_good_' in run else 'bad'
    for s in EF.segments(pd.read_csv(f)):
        seg = s['seg'].reset_index(drop=True)
        if len(seg) < 2:
            continue
        for method in RULES:
            facts = words(method, seg, s['prev'])
            if s['phase'] in RULES[method]:
                ok = fires(RULES[method][s['phase']], facts)
                rows.append(dict(method=method, run=run, quality=quality, phase=s['phase'], k=s['k'],
                                 matches='yes' if ok else 'no', facts=short(facts)))
            else:  # e.g. wall_following_fail: which phase rules match here?
                hit = [p for p, r in RULES[method].items() if fires(r, facts)]
                rows.append(dict(method=method, run=run, quality=quality, phase=s['phase'], k=s['k'],
                                 matches='(no own rule) matches: ' + (', '.join(hit) or 'none'),
                                 facts=short(facts)))
t = pd.DataFrame(rows)
os.makedirs('bad_run_test', exist_ok=True)
t.to_csv('bad_run_test/entry_rules_per_occurrence.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 120)

print('=== Does the phase rule match?  (count of phase occurrences) ===')
s = t[t.matches.isin(['yes', 'no'])]
summ = (s.groupby(['phase', 'method', 'quality'])['matches']
          .agg(lambda x: f"{(x == 'yes').sum()}/{len(x)}").unstack('quality').unstack('method'))
print(summ.to_string())

print(f'\n=== One bad run in detail: {DETAIL_RUN} ===')
d = t[t.run == DETAIL_RUN]
print(d[['method', 'phase', 'k', 'matches', 'facts']].to_string(index=False))

print('\n=== Phases without an own rule in bad runs (e.g. wall_following_fail) ===')
x = t[(t.quality == 'bad') & ~t.matches.isin(['yes', 'no'])]
print(x[['method', 'run', 'phase', 'matches']].to_string(index=False) if len(x) else 'none')
print('\nSaved: bad_run_test/entry_rules_per_occurrence.csv')