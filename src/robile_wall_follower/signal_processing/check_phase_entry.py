#!/usr/bin/env python3
"""
check_phase_entry.py  -  look at lidar_left AROUND each phase change (pillar good runs)

For every phase segment (consecutive rows with the same label) it prints:
  before  = mean of the last 5 rows of the previous segment
  start   = mean of the first 5 rows of this segment
  end     = mean of the last 5 rows of this segment
  jump    = start - before   (what happens AT the border)
  inside  = end - start      (what happens INSIDE the phase)
Nothing is changed, it only prints.

HOW TO RUN
  cd ~/rnd_ws/src/robile_wall_follower/signal_processing
  python3 check_phase_entry.py
"""
import os, glob
import pandas as pd

CLEANED_DIR = os.path.expanduser('~/rnd_ws/data_cleaned')
N = 5
rows = []
for f in sorted(glob.glob(os.path.join(CLEANED_DIR, 'pill_good_*.csv'))):
    run = '_'.join(os.path.basename(f).split('_')[:3])
    df = pd.read_csv(f).reset_index(drop=True)
    seg = (df['action_label'] != df['action_label'].shift()).cumsum()
    segs = [g for _, g in df.groupby(seg, sort=True)]
    for i, g in enumerate(segs):
        ph = g['action_label'].iloc[0]
        if ph in ('idle', 'searching_wall'):
            continue
        v = g['lidar_left'].values
        before = segs[i-1]['lidar_left'].values[-N:].mean() if i > 0 else float('nan')
        start, end = v[:N].mean(), v[-N:].mean()
        rows.append(dict(run=run, phase=ph, rows=len(v), before=before, start=start, end=end,
                         jump=start - before, inside=end - start))
t = pd.DataFrame(rows)
pd.set_option('display.width', 200)
order = ['approaching_wall', 'wall_following', 'obstacle_detected', 'obstacle_avoidance', 'wall_reacquired']
for ph in order:
    s = t[t.phase == ph]
    print(f'\n=== {ph}  ({len(s)} segments in 7 runs) ===')
    print(s[['run', 'rows', 'before', 'start', 'end', 'jump', 'inside']].round(2).to_string(index=False))