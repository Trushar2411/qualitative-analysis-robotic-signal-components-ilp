#!/usr/bin/env python3
"""
why_bad.py  -  what makes each bad run 'bad'? (only prints, changes nothing)

Per run it summarises lidar_left (distance to the wall) and lidar_front:
  rows          number of rows (excluding idle / searching_wall)
  fail_rows     rows the controller itself labelled wall_following_fail
  pillar_passes how many times obstacle_detected occurs
  in_zone_%     share of rows with lidar_left inside the controller's band (0.40-0.65 m)
  too_close_%   share of rows with lidar_left < 0.40 m
  too_far_%     share of rows with lidar_left > 0.65 m
  left_median   typical wall distance
  front_min     closest thing in front (danger if very small)
Good runs are printed first as the reference.

HOW TO RUN
  cd ~/rnd_ws/src/robile_wall_follower/signal_processing
  python3 why_bad.py
"""
import os, glob
import pandas as pd

CLEANED_DIR = os.path.expanduser('~/rnd_ws/data_cleaned')
rows = []
for f in sorted(glob.glob(os.path.join(CLEANED_DIR, '*.csv'))):
    run = '_'.join(os.path.basename(f).split('_')[:3])
    df = pd.read_csv(f)
    df = df[~df['action_label'].isin(['idle', 'searching_wall'])]
    if df.empty or 'lidar_left' not in df:
        continue
    L = df['lidar_left']
    seg = (df['action_label'] != df['action_label'].shift()).cumsum()
    occ = df.groupby(seg)['action_label'].first()
    rows.append(dict(
        run=run,
        quality='good' if '_good_' in run else 'bad',
        rows=len(df),
        fail_rows=int((df['action_label'] == 'wall_following_fail').sum()),
        pillar_passes=int((occ == 'obstacle_detected').sum()),
        in_zone_pct=round(100 * L.between(0.40, 0.65).mean()),
        too_close_pct=round(100 * (L < 0.40).mean()),
        too_far_pct=round(100 * (L > 0.65).mean()),
        left_median=round(L.median(), 2),
        front_min=round(df['lidar_front'].min(), 2) if 'lidar_front' in df else None,
    ))
t = pd.DataFrame(rows).sort_values(['quality', 'run'], ascending=[False, True])
pd.set_option('display.width', 200)
for q in ['good', 'bad']:
    print(f'\n=== {q.upper()} runs ===')
    print(t[t.quality == q].drop(columns='quality').to_string(index=False))