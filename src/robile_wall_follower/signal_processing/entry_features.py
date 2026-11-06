#!/usr/bin/env python3
"""
entry_features.py  -  shared helper for the ENTRY experiment (RAW + QTA copies)

1) Splits each run into phase OCCURRENCES (segments): consecutive rows with the
   same action_label. Two wall_following pieces = two examples.
2) Entry fact per lidar: what happens AT THE START of a segment, compared with
   the end of the previous segment:
      jump  = mean(first 5 rows of this segment) - mean(last 5 rows of previous)
      jump >  +0.10 m -> 'jump_up'
      jump <  -0.10 m -> 'jump_down'
      otherwise       -> 'no_jump'
   No entry fact if there is no previous segment, or it is idle / searching_wall.
   Same 0.10 m limit for all four lidars (well above lidar noise of a few cm).
3) apply_qta(): same logic as qta_visualizer.py (with the trend-first fix).

Run it directly to CHECK the entry labels before running Popper:
  python3 entry_features.py
"""
import os, glob
import numpy as np
import pandas as pd

CLEANED_DIR = os.path.expanduser('~/rnd_ws/data_cleaned')
EXCLUDED    = ['idle', 'searching_wall']
SENSORS     = ['lidar_left', 'lidar_right', 'lidar_front', 'lidar_front_right']
N_EDGE      = 5
JUMP        = 0.10

# --- same thresholds as qta_visualizer.py ---
SLOPE_THRESHOLD    = 0.005
CONSTANT_THRESHOLD = 0.05
ZERO_THRESHOLD     = 0.02


def apply_qta(values):
    values = np.array(values, dtype=float)
    valid = values[~np.isnan(values)]
    if len(valid) < 3:
        return 'is_zero'
    mean_val = np.mean(valid)
    std_val = np.std(valid)
    if abs(mean_val) < ZERO_THRESHOLD:
        return 'is_zero'
    cv = std_val / abs(mean_val) if abs(mean_val) > 0 else std_val
    if cv < CONSTANT_THRESHOLD:
        return 'is_constant'
    x = np.arange(len(valid))
    slope = np.polyfit(x, valid, 1)[0]
    ns = slope / abs(mean_val) if abs(mean_val) > 0 else slope
    if ns > SLOPE_THRESHOLD:
        return 'is_increasing'
    elif ns < -SLOPE_THRESHOLD:
        return 'is_decreasing'
    if cv > 0.15:
        return 'is_oscillating'
    return 'is_constant'


def segments(df):
    """List of occurrences: dict(phase, k, seg, prev). Excluded phases are skipped
    (but still count as 'previous', so no entry fact is made after them)."""
    df = df.reset_index(drop=True)
    seg_id = (df['action_label'] != df['action_label'].shift()).cumsum()
    parts = [g for _, g in df.groupby(seg_id, sort=True)]
    out, count = [], {}
    for i, g in enumerate(parts):
        ph = g['action_label'].iloc[0]
        if ph in EXCLUDED:
            continue
        prev = parts[i - 1] if i > 0 else None
        if prev is not None and prev['action_label'].iloc[0] in EXCLUDED:
            prev = None
        count[ph] = count.get(ph, 0) + 1
        out.append(dict(phase=ph, k=count[ph], seg=g, prev=prev))
    return out


def entry_label(seg, prev, sensor):
    if prev is None or sensor not in seg.columns or sensor not in prev.columns:
        return None
    a = prev[sensor].values[-N_EDGE:]
    b = seg[sensor].values[:N_EDGE]
    if np.isnan(a).all() or np.isnan(b).all():
        return None
    jump = np.nanmean(b) - np.nanmean(a)
    if jump > JUMP:
        return 'jump_up'
    if jump < -JUMP:
        return 'jump_down'
    return 'no_jump'


def find_csv(run_id):
    hits = sorted(glob.glob(os.path.join(CLEANED_DIR, f'{run_id}_*.csv')))
    return hits[0] if hits else None


if __name__ == '__main__':
    # quick check: lidar_left entry label + QTA trend per phase occurrence, good runs
    rows = []
    for f in sorted(glob.glob(os.path.join(CLEANED_DIR, '*_good_*.csv'))):
        run = '_'.join(os.path.basename(f).split('_')[:3])
        for s in segments(pd.read_csv(f)):
            rows.append(dict(task='pillar' if run.startswith('pill') else 'plain', phase=s['phase'],
                             entry=entry_label(s['seg'], s['prev'], 'lidar_left') or 'none',
                             qta=apply_qta(s['seg']['lidar_left'].values).replace('is_', '')))
    t = pd.DataFrame(rows)
    for task in ['plain', 'pillar']:
        print(f'\n=== {task}: lidar_left ENTRY label per phase occurrence (good runs) ===')
        print(t[t.task == task].groupby(['phase', 'entry']).size().unstack(fill_value=0).to_string())
        print(f'\n=== {task}: lidar_left QTA trend per phase occurrence ===')
        print(t[t.task == task].groupby(['phase', 'qta']).size().unstack(fill_value=0).to_string())