#!/usr/bin/env python3
"""
make_levels.py  -  distance level per run, phase and lidar (shared by RAW and QTA)

Limits come from the controller (wall_follower_node.py):
    TARGET_DISTANCE = 0.5 m
    left > TARGET + 0.15  -> controller treats it as too far   -> 'far'
    left < TARGET - 0.10  -> controller treats it as too close -> 'near'
    otherwise                                                   -> 'at_target'
The SAME limits are used for all four lidars (nothing singled out).
The level uses the MEDIAN of the phase (robust to the 10 m capped readings).

HOW TO RUN
  cd ~/rnd_ws/src/robile_wall_follower/signal_processing
  python3 make_levels.py
OUTPUT
  ~/rnd_ws/levels/levels.json   {run: {phase: {sensor: level}}}
"""
import os, glob, json
import pandas as pd

CLEANED_DIR = os.path.expanduser('~/rnd_ws/data_cleaned')
OUT_FILE    = os.path.expanduser('~/rnd_ws/levels/levels.json')
TARGET      = 0.5
NEAR_BELOW  = TARGET - 0.10     # 0.40 m  (controller: too close)
FAR_ABOVE   = TARGET + 0.15     # 0.65 m  (controller: too far)
SENSORS     = ['lidar_left', 'lidar_right', 'lidar_front', 'lidar_front_right']
EXCLUDED    = ['idle', 'searching_wall']


def level(median):
    if median < NEAR_BELOW:
        return 'near'
    if median > FAR_ABOVE:
        return 'far'
    return 'at_target'


def main():
    out, rows = {}, []
    for f in sorted(glob.glob(os.path.join(CLEANED_DIR, '*.csv'))):
        run = '_'.join(os.path.basename(f).split('_')[:3])      # e.g. pill_good_01
        df = pd.read_csv(f)
        df = df[~df['action_label'].isin(EXCLUDED)]
        out[run] = {}
        for phase, g in df.groupby('action_label', sort=False):
            out[run][phase] = {}
            for s in SENSORS:
                if s in g.columns and g[s].notna().any():
                    med = float(g[s].median())
                    out[run][phase][s] = level(med)
                    rows.append(dict(run=run, phase=phase, sensor=s, median=round(med, 2), level=level(med)))
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    json.dump(out, open(OUT_FILE, 'w'), indent=1)

    t = pd.DataFrame(rows)
    good = t[t.run.str.contains('_good_') & (t.sensor == 'lidar_left')]
    print(f'Limits: near < {NEAR_BELOW:.2f} m <= at_target <= {FAR_ABOVE:.2f} m < far\n')
    print('lidar_left level per phase, GOOD runs (count of runs):')
    print(good.groupby(['phase', 'level']).size().unstack(fill_value=0).to_string())
    print('\nlidar_left median per phase, GOOD runs (min - max):')
    print(good.groupby('phase')['median'].agg(['min', 'max']).to_string())
    print(f'\nSaved: {OUT_FILE}')


if __name__ == '__main__':
    main()