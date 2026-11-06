#!/usr/bin/env python3
"""
plot_along_wall.py  -  where was the robot, sideways, in each phase?

The data has pos_x (how far along the wall) but no pos_y (sideways), so the
sideways movement is read from the two side lidars:
  robot moves RIGHT (away from left wall) -> lidar_left UP,   lidar_right DOWN
  robot moves LEFT  (toward left wall)    -> lidar_left DOWN, lidar_right UP
If the two lidars move in opposite directions, the ROBOT moved
(not just a different object in front of one lidar).

Output: along_wall_plots/along_<run>.png  and a table of changes per phase.
"""
import os, glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

CLEANED_DIR = os.path.expanduser('~/rnd_ws/data_cleaned')
OUT = 'along_wall_plots'
PHASES = ['approaching_wall', 'wall_following', 'obstacle_detected',
          'obstacle_avoidance', 'wall_reacquired']
COLORS = dict(zip(PHASES, ['#2a78d6', '#1baf7a', '#e34948', '#eda100', '#6250d6']))
INK, MUTED = '#14213D', '#5A647A'


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for f in sorted(glob.glob(os.path.join(CLEANED_DIR, 'pill_good_*.csv'))):
        run = '_'.join(os.path.basename(f).split('_')[:3])
        df = pd.read_csv(f)
        df = df[~df['action_label'].isin(['idle', 'searching_wall'])].reset_index(drop=True)
        seg = (df['action_label'] != df['action_label'].shift()).cumsum()

        # change of each side lidar inside every pillar-phase occurrence
        for _, g in df.groupby(seg):
            ph = g['action_label'].iloc[0]
            if ph in ('obstacle_avoidance', 'wall_reacquired') or (ph == 'approaching_wall' and g.index[0] > 50):
                rows.append(dict(run=run, phase=ph,
                                 left_change=g.lidar_left.values[-3:].mean() - g.lidar_left.values[:3].mean(),
                                 right_change=g.lidar_right.values[-3:].mean() - g.lidar_right.values[:3].mean(),
                                 metres_forward=g.pos_x.values[-1] - g.pos_x.values[0]))

        # plot: x = pos_x, top = lidar_left, bottom = lidar_right
        fig, (a1, a2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
        for ax, col, txt in [(a1, 'lidar_left', 'lidar_left: distance to the LEFT (wall / pillar)'),
                             (a2, 'lidar_right', 'lidar_right: distance to the RIGHT')]:
            for _, g in df.groupby(seg):
                ph = g['action_label'].iloc[0]
                ax.axvspan(g.pos_x.min(), g.pos_x.max(), color=COLORS.get(ph, '#DDDDDD'), alpha=0.2, lw=0)
            ax.plot(df.pos_x, df[col], color=INK, lw=1.8)
            ax.set_ylabel(f'{col} (m)')
            ax.set_title(txt, loc='left', fontsize=11, color=INK)
            for sp in ['top', 'right']:
                ax.spines[sp].set_visible(False)
        a2.set_xlabel('pos_x: how far the robot has driven along the wall (m)')
        fig.suptitle(f'{run}: side distances along the route', x=0.01, ha='left', color=INK)
        fig.legend(handles=[Patch(color=COLORS[p], alpha=0.4, label=p) for p in PHASES],
                   loc='lower center', ncol=5, frameon=False)
        fig.subplots_adjust(bottom=0.14, hspace=0.3)
        fig.savefig(f'{OUT}/along_{run}.png', dpi=140); plt.close(fig)

    t = pd.DataFrame(rows)
    pd.set_option('display.width', 200)
    print('Change INSIDE each phase (end minus start), metres:')
    print(t.round(2).to_string(index=False))
    print('\nAverage per phase:')
    print(t.groupby('phase')[['left_change', 'right_change', 'metres_forward']].mean().round(2).to_string())
    print(f'\nSaved plots in {OUT}/')


if __name__ == '__main__':
    main()