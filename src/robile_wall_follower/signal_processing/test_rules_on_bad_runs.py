#!/usr/bin/env python3
"""
test_rules_on_bad_runs.py  -  apply the learned rules to good AND bad runs

NOTHING IS LEARNED HERE. We take the rules Popper learned from the GOOD runs
(combined task, current results) and check, for every run and every phase in it:
    does the rule of that phase fire?

Good runs  -> should fire (this is the training recall, a sanity check)
Bad runs   -> if the rule does NOT fire, the rule "notices" the bad behaviour

Labels:
  RAW : recomputed here from data_cleaned/ with the same dominant-change logic
        as ilp_raw_loocv.py (threshold 0.01, oscillating if minority > 20%)
  QTA : read from qta_results/*_qta.json (made by qta_visualizer.py)

HOW TO RUN
  cd ~/rnd_ws/src/robile_wall_follower/signal_processing
  python3 test_rules_on_bad_runs.py
OUTPUT
  printed tables + bad_run_test/rule_firing_per_run.csv
"""
import os, glob, json
import pandas as pd

CLEANED_DIR = os.path.expanduser('~/rnd_ws/data_cleaned')
QTA_DIR     = os.path.expanduser('~/rnd_ws/qta_results')
OUT_DIR     = 'bad_run_test'
THRESHOLD   = 0.01
EXCLUDED    = ['idle', 'searching_wall']
SENSORS     = ['lidar_left', 'lidar_right', 'lidar_front', 'lidar_front_right']
NOTE_RUNS   = {'pill_bad_02': 'lidar_left/right mostly invalid (63-68% capped)'}

# short names used in the rules below
L, R, F, FR = 'lidar_left', 'lidar_right', 'lidar_front', 'lidar_front_right'

# ---------------------------------------------------------------------------
# Current rules, COMBINED task (learned on all 17 good runs).
# A rule = list of clauses (OR). A clause = list of (sensor, label) (AND).
# RAW had alternatives across the 10 Popper runs -> each alternative tested.
# ---------------------------------------------------------------------------
RULES = {
    'RAW': {
        'approaching_wall':   {'A: left decreasing [6/10]':  [[(L, 'decreasing')]],
                               'B: right increasing [4/10]': [[(R, 'increasing')]]},
        'wall_following':     {'A: left const + front dec [5/10]': [[(L, 'constant'), (F, 'decreasing')]],
                               'B: front dec + fr const [5/10]':   [[(F, 'decreasing'), (FR, 'constant')]]},
        'obstacle_detected':  {'left const + fr oscillating': [[(L, 'constant'), (FR, 'oscillating')]]},
        'obstacle_avoidance': {'left increasing':  [[(L, 'increasing')]]},
        'wall_reacquired':    {'left oscillating': [[(L, 'oscillating')]]},
    },
    'QTA': {
        'approaching_wall':   {'left decreasing':        [[(L, 'decreasing')]]},
        'wall_following':     {'front_right oscillating': [[(FR, 'oscillating')]]},
        'obstacle_detected':  {'(fr const + r const) OR (left const + r dec)':
                               [[(FR, 'constant'), (R, 'constant')], [(L, 'constant'), (R, 'decreasing')]]},
        'obstacle_avoidance': {'left inc + front const/inc':
                               [[(L, 'increasing'), (F, 'constant')], [(L, 'increasing'), (F, 'increasing')]]},
        'wall_reacquired':    {'left const + fr/r inc OR front dec + fr dec':
                               [[(L, 'constant'), (FR, 'increasing')], [(L, 'constant'), (R, 'increasing')],
                                [(F, 'decreasing'), (FR, 'decreasing')]]},
    },
}


# ---------------------------------------------------------------------------
# RAW labels (same logic as ilp_raw_loocv.py)
# ---------------------------------------------------------------------------
def get_dominant_label(values, threshold):
    inc = dec = con = 0
    for i in range(len(values) - 1):
        v1, v2 = values[i], values[i + 1]
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
    if inc > 0 and dec > 0 and min(inc, dec) / total > 0.2:
        return 'oscillating'
    if dec > inc and dec > con:
        return 'decreasing'
    if inc > dec and inc > con:
        return 'increasing'
    return 'constant'


def raw_labels():
    out = {}
    for f in sorted(glob.glob(os.path.join(CLEANED_DIR, '*.csv'))):
        run = '_'.join(os.path.basename(f).split('_')[:3])          # pw_good_01
        df = pd.read_csv(f)
        df = df[~df['action_label'].isin(EXCLUDED)]
        out[run] = {}
        for phase, g in df.groupby('action_label', sort=False):
            out[run][phase] = {s: get_dominant_label(g[s].values, THRESHOLD)
                               for s in SENSORS if s in g.columns}
    return out


def qta_labels():
    out = {}
    for f in sorted(glob.glob(os.path.join(QTA_DIR, '*_qta.json'))):
        d = json.load(open(f))
        if isinstance(d, list):
            d = d[0]
        run = d['run_id']
        out[run] = {}
        for phase, sensors in d['windows'].items():
            if phase in EXCLUDED:
                continue
            out[run][phase] = {s: v['shape'].replace('is_', '')
                               for s, v in sensors.items() if s in SENSORS}
    return out


def fires(rule, labels):
    return any(all(labels.get(s) == lab for s, lab in clause) for clause in rule)


# ---------------------------------------------------------------------------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    labels = {'RAW': raw_labels(), 'QTA': qta_labels()}
    rows = []
    for method, runs in labels.items():
        for run, phases in runs.items():
            quality = 'good' if '_good_' in run else 'bad' if '_bad_' in run else '?'
            for phase, lab in phases.items():
                if phase in RULES[method]:
                    for name, rule in RULES[method][phase].items():
                        rows.append(dict(method=method, run=run, quality=quality, phase=phase,
                                         rule=name, fires=fires(rule, lab),
                                         labels=' | '.join(f"{s.replace('lidar_','')}={lab.get(s)}" for s in SENSORS)))
                else:
                    # a phase with no rule (e.g. wall_following_fail): which phase rules fire here?
                    hit = [f'{p}' for p, alts in RULES[method].items()
                           if any(fires(r, lab) for r in alts.values())]
                    rows.append(dict(method=method, run=run, quality=quality, phase=phase,
                                     rule='(no own rule) rules that fire: ' + (', '.join(hit) or 'none'),
                                     fires=None,
                                     labels=' | '.join(f"{s.replace('lidar_','')}={lab.get(s)}" for s in SENSORS)))
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(OUT_DIR, 'rule_firing_per_run.csv'), index=False)

    pd.set_option('display.width', 220); pd.set_option('display.max_colwidth', 80)
    # ---- summary: how often does each rule fire, good vs bad ----
    print('\n=== How often does the phase rule fire?  (good = training recall, bad = new test) ===')
    s = res[res.fires.notna()].copy()
    s['fires'] = s['fires'].astype(int)
    summ = (s.groupby(['method', 'phase', 'rule', 'quality'])['fires']
              .agg(lambda x: f'{x.sum()}/{len(x)}').unstack('quality').reset_index())
    print(summ.to_string(index=False))

    # ---- details for bad runs ----
    print('\n=== Bad runs, phase by phase ===')
    b = res[res.quality == 'bad'].copy()
    b['fires'] = b['fires'].map({True: 'FIRES', False: 'no', None: '-'})
    b['note'] = b['run'].map(NOTE_RUNS).fillna('')
    print(b[['method', 'run', 'phase', 'rule', 'fires', 'labels', 'note']].to_string(index=False))
    print(f'\nSaved: {OUT_DIR}/rule_firing_per_run.csv')


if __name__ == '__main__':
    main()