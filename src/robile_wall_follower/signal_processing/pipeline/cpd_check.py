#!/usr/bin/env python3
"""
cpd_check.py  -  Change Point Detection (CPD) check for sensor selection
=========================================================================

WHAT THIS SCRIPT DOES (simple version)
--------------------------------------
For every raw run (good AND bad, plain wall AND pillar wall) and for every sensor:

  1. Take the sensor signal on its own (no action_label used here).
  2. Run classical CPD (PELT algorithm from the 'ruptures' library).
     PELT searches for the points where the signal changes its behaviour
     (model 'clinear': where a straight-line piece ends, e.g. ramp -> flat).
  3. Compare the change points CPD found with the REAL phase boundaries
     (rows where action_label changes).
       - hit rate (recall)  = how many real phase boundaries were found by CPD
       - precision          = how many CPD change points are close to a real boundary
       - F1                 = one number combining both
     "Close" means within +/- TOLERANCE rows.
  4. Average over runs, separately for good runs, bad runs and all runs.

A sensor is USEFUL if its change points line up with the phase boundaries
(high hit rate AND high precision). A noisy sensor (e.g. IMU) gives change
points at random places -> low precision. A sensor that never reacts gives
no change points -> low hit rate.

CHANCE LEVEL: if CPD put change points at random rows, its precision would
be about 'chance_precision' (printed for each group). A useful sensor must
be clearly above that.

HOW TO RUN
----------
    pip install ruptures --break-system-packages      (only once)
    cd ~/rnd_ws/src/robile_wall_follower/signal_processing
    python3 cpd_check.py

OUTPUT (folder cpd_results/)
----------------------------
    cpd_per_run.csv   one row per (run, sensor)
    cpd_summary.csv   one row per (group, sensor) with averages + KEEP/DROP
    printed tables in the terminal
"""

import os
import glob
import numpy as np
import pandas as pd
import ruptures as rpt

# ----------------------------------------------------------------------------
# CONFIG  (same folders and sensors as signal_processor.py)
# ----------------------------------------------------------------------------
PLAIN_WALL_DIR  = os.path.expanduser('~/rnd_ws/data')
PILLAR_WALL_DIR = os.path.expanduser('~/rnd_ws/data_pillar')
CLEANED_DIR     = os.path.expanduser('~/rnd_ws/data_cleaned')   # only used to find good/bad names
OUTPUT_DIR      = 'cpd_results'

ALL_SENSORS = [
    'lidar_left', 'lidar_right', 'lidar_front', 'lidar_front_right',
    'odom_linear_x', 'odom_angular_z', 'pos_x', 'pos_y',
    'cmd_linear_x', 'cmd_angular_z',
    'imu_angular_z', 'imu_accel_x', 'imu_accel_y',
    'wheel_speed_0', 'wheel_speed_1', 'wheel_speed_2', 'wheel_speed_3',
    'distance_travelled',
]

TOLERANCE     = 10    # rows; same size as EVENT_WINDOW in signal_processor.py
CPD_MODEL     = 'clinear'  # 'clinear' = signal is straight-line pieces (ramps + flat parts), fits lidar best
                            # 'l2'      = signal is flat pieces with jumps in the mean
PENALTY_SCALE = 10.0   # PELT penalty = PENALTY_SCALE * noise_variance * log(n). Higher -> fewer change points
MIN_SIZE      = 5     # smallest segment (rows) PELT may create
IGNORE_LABELS = []    # e.g. ['idle'] if you want to ignore idle boundaries

# Decision rule (on GOOD runs, because those are the runs we train on)
KEEP_MIN_HIT_RATE     = 0.5   # finds at least half the phase boundaries
KEEP_MIN_PRECISION_X  = 1.5   # precision at least 1.5x chance level


# ----------------------------------------------------------------------------
# 1. Find raw files and give them a name + good/bad + scenario
# ----------------------------------------------------------------------------
def to_time(col):
    """Timestamps can be numbers (1720528710.8) or text ('2026-07-09 12:18:30.804').
    Turn both into real pandas time values so they can be compared."""
    num = pd.to_numeric(col, errors='coerce')
    if num.notna().mean() > 0.9:
        return pd.to_datetime(num, unit='s', errors='coerce')
    return pd.to_datetime(col, errors='coerce')


def build_cleaned_index():
    """Read data_cleaned/*.csv (pw_good_01_plain_wall.csv ...) and remember
    their timestamps, so we can find which raw file is which run."""
    index = []
    for f in sorted(glob.glob(os.path.join(CLEANED_DIR, '*.csv'))):
        try:
            df = pd.read_csv(f, usecols=['timestamp', 'run_id'])
        except Exception:
            continue
        if len(df) == 0:
            continue
        index.append({
            'run_id': str(df['run_id'].iloc[0]),
            'ts_mid': to_time(df['timestamp']).iloc[len(df) // 2],
        })
    return index


def name_raw_file(path, raw_df, cleaned_index, scenario):
    """Return (run_name, quality). quality is 'good', 'bad' or 'unknown'."""
    base = os.path.basename(path).lower()
    # a) filename already says it
    for q in ('good', 'bad'):
        if q in base:
            return os.path.splitext(os.path.basename(path))[0], q
    # b) match with the cleaned file whose middle timestamp lies inside this raw file
    if 'timestamp' in raw_df.columns and len(raw_df):
        ts = to_time(raw_df['timestamp'])
        t0, t1 = ts.min(), ts.max()
        for c in cleaned_index:
            if pd.notna(c['ts_mid']) and t0 <= c['ts_mid'] <= t1:
                q = 'good' if '_good_' in c['run_id'] else ('bad' if '_bad_' in c['run_id'] else 'unknown')
                return c['run_id'], q
    # c) unknown
    return f"{scenario}_{os.path.splitext(os.path.basename(path))[0]}", 'unknown'


def load_all_runs():
    cleaned_index = build_cleaned_index()
    runs = []
    for folder, scenario in [(PLAIN_WALL_DIR, 'plain'), (PILLAR_WALL_DIR, 'pillar')]:
        for f in sorted(glob.glob(os.path.join(folder, '*.csv'))):
            df = pd.read_csv(f)
            if 'action_label' not in df.columns:
                print(f"  skip (no action_label): {f}")
                continue
            name, quality = name_raw_file(f, df, cleaned_index, scenario)
            runs.append({'name': name, 'quality': quality, 'scenario': scenario,
                         'file': f, 'df': df.reset_index(drop=True)})
    return runs


# ----------------------------------------------------------------------------
# 2. Real phase boundaries (from action_label)
# ----------------------------------------------------------------------------
def true_boundaries(df):
    labels = df['action_label'].astype(str).values
    b = []
    for i in range(1, len(labels)):
        if labels[i] != labels[i - 1]:
            if labels[i] in IGNORE_LABELS and labels[i - 1] in IGNORE_LABELS:
                continue
            b.append(i)
    return b


# ----------------------------------------------------------------------------
# 3. CPD on one sensor signal
# ----------------------------------------------------------------------------
def detect_change_points(signal):
    """PELT on the z-scored signal. Returns list of row indices.
    Returns None if the signal is flat (nothing to detect)."""
    x = pd.to_numeric(pd.Series(signal), errors='coerce')
    if x.isna().all():
        return None
    x = x.interpolate().bfill().ffill().values      # fill gaps so row numbers stay the same
    if len(x) < 2 * MIN_SIZE or np.std(x) < 1e-9:
        return None
    z = (x - x.mean()) / x.std()
    # noise level estimated from row-to-row differences (robust to the real changes)
    noise_sd = np.median(np.abs(np.diff(z))) / 0.6745 / np.sqrt(2)
    noise_sd = max(noise_sd, 0.01)                  # floor, so very clean signals don't explode
    algo = rpt.Pelt(model=CPD_MODEL, min_size=MIN_SIZE, jump=1).fit(z.reshape(-1, 1))
    cps = algo.predict(pen=PENALTY_SCALE * noise_sd ** 2 * np.log(len(z)))
    return [c for c in cps if c < len(z)]          # last element is always len(z)


# ----------------------------------------------------------------------------
# 4. Compare detected vs real boundaries
# ----------------------------------------------------------------------------
def match_scores(detected, truth, n_rows):
    if not truth:
        return None
    if not detected:
        return dict(hit_rate=0.0, precision=0.0, f1=0.0, n_cp=0)
    hits = sum(any(abs(d - t) <= TOLERANCE for d in detected) for t in truth)
    good = sum(any(abs(d - t) <= TOLERANCE for t in truth) for d in detected)
    hr = hits / len(truth)
    pr = good / len(detected)
    f1 = 0.0 if hr + pr == 0 else 2 * hr * pr / (hr + pr)
    return dict(hit_rate=hr, precision=pr, f1=f1, n_cp=len(detected))


def chance_precision(truth, n_rows):
    """Fraction of rows that are within TOLERANCE of a real boundary.
    = precision a random change point would get."""
    near = np.zeros(n_rows, dtype=bool)
    for t in truth:
        near[max(0, t - TOLERANCE): min(n_rows, t + TOLERANCE + 1)] = True
    return near.mean()


# ----------------------------------------------------------------------------
# 5. Main
# ----------------------------------------------------------------------------
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    runs = load_all_runs()
    print(f"\nLoaded {len(runs)} runs")
    for r in runs:
        print(f"  {r['name']:<28} {r['quality']:<8} {r['scenario']:<7} rows={len(r['df'])}")

    rows = []
    for r in runs:
        df = r['df']
        truth = true_boundaries(df)
        n = len(df)
        chance = chance_precision(truth, n) if truth else np.nan
        for s in ALL_SENSORS:
            base = dict(run=r['name'], quality=r['quality'], scenario=r['scenario'],
                        sensor=s, n_rows=n, n_boundaries=len(truth), chance_precision=chance)
            if s not in df.columns:
                rows.append({**base, 'status': 'missing'})
                continue
            cps = detect_change_points(df[s].values)
            if cps is None:
                rows.append({**base, 'status': 'flat', 'hit_rate': 0.0, 'precision': 0.0,
                             'f1': 0.0, 'n_cp': 0})
                continue
            m = match_scores(cps, truth, n)
            if m is None:
                rows.append({**base, 'status': 'no_labels', 'n_cp': len(cps)})
            else:
                rows.append({**base, 'status': 'ok', **m})

    per_run = pd.DataFrame(rows)
    per_run.to_csv(os.path.join(OUTPUT_DIR, 'cpd_per_run.csv'), index=False)

    # ---- summary per group ------------------------------------------------
    summaries = []
    groups = {
        'good_plain':  (per_run.quality == 'good') & (per_run.scenario == 'plain'),
        'good_pillar': (per_run.quality == 'good') & (per_run.scenario == 'pillar'),
        'good_all':    (per_run.quality == 'good'),
        'bad_all':     (per_run.quality == 'bad'),
        'all_runs':    per_run.quality.notna(),
    }
    for gname, mask in groups.items():
        g = per_run[mask & per_run.status.isin(['ok', 'flat'])]
        if g.empty:
            continue
        chance = g.drop_duplicates('run')['chance_precision'].mean()
        agg = g.groupby('sensor').agg(runs=('run', 'nunique'),
                                      hit_rate=('hit_rate', 'mean'),
                                      precision=('precision', 'mean'),
                                      f1=('f1', 'mean'),
                                      avg_cps=('n_cp', 'mean')).reset_index()
        agg['chance_precision'] = chance
        agg['precision_x_chance'] = agg['precision'] / chance if chance > 0 else np.nan
        agg['decision'] = np.where((agg.hit_rate >= KEEP_MIN_HIT_RATE) &
                                   (agg.precision_x_chance >= KEEP_MIN_PRECISION_X),
                                   'KEEP', 'DROP')
        agg.insert(0, 'group', gname)
        summaries.append(agg.sort_values('f1', ascending=False))

    if not summaries:
        print("\nNo runs with action_label boundaries found. Check folders/paths.")
        return
    summary = pd.concat(summaries, ignore_index=True)
    summary.to_csv(os.path.join(OUTPUT_DIR, 'cpd_summary.csv'), index=False)

    pd.set_option('display.width', 160)
    for gname, g in summary.groupby('group', sort=False):
        print(f"\n=== {gname}  (runs={g.runs.max()}, chance precision={g.chance_precision.iloc[0]:.2f}) ===")
        print(g[['sensor', 'hit_rate', 'precision', 'precision_x_chance', 'f1', 'avg_cps', 'decision']]
              .to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    # ---- compare good vs bad ----------------------------------------------
    print("\n=== Sensors KEPT by CPD (good runs) vs bad runs ===")
    gk = set(summary[(summary.group == 'good_all') & (summary.decision == 'KEEP')].sensor)
    bk = set(summary[(summary.group == 'bad_all') & (summary.decision == 'KEEP')].sensor)
    print("  good runs keep :", sorted(gk))
    print("  bad runs keep  :", sorted(bk))
    print("  only in good   :", sorted(gk - bk))
    print("  only in bad    :", sorted(bk - gk))
    print(f"\nSaved: {OUTPUT_DIR}/cpd_per_run.csv and {OUTPUT_DIR}/cpd_summary.csv")


if __name__ == '__main__':
    main()