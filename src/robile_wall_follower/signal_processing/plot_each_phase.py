#!/usr/bin/env python3
"""
plot_each_phase.py  -  each phase on its own, all 7 good pillar runs on top of each other

One figure, 5 columns (one per phase, in driving order) x 2 rows (lidar_left, lidar_right).
In each small plot:
  0 s          = the moment the phase starts (dashed line)
  grey line    = the last 1 s BEFORE the phase (to see jumps at the start)
  coloured line= inside the phase; one line per phase occurrence
wall_following and approaching_wall are long, so only their first 8 s are shown.

Output: phase_panels.png
"""
import os, glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CLEANED_DIR = os.path.expanduser('~/rnd_ws/data_cleaned')
ORDER = ['wall_following', 'obstacle_detected', 'obstacle_avoidance',
         'wall_reacquired', 'approaching_wall']
COLORS = dict(zip(['approaching_wall', 'wall_following', 'obstacle_detected',
                   'obstacle_avoidance', 'wall_reacquired'],
                  ['#2a78d6', '#1baf7a', '#e34948', '#eda100', '#6250d6']))
# SENSORS = [('lidar_left', 'lidar_left (m)\nLEFT side: wall / pillar'),
#            ('lidar_right', 'lidar_right (m)\nRIGHT side')]
SENSORS = [('lidar_left', 'lidar_left (m)\nLEFT'),
           ('lidar_right', 'lidar_right (m)\nRIGHT'),
           ('lidar_front', 'lidar_front (m)\nFRONT'),
           ('lidar_front_right', 'lidar_front_right (m)\nFRONT-RIGHT')]
INK, MUTED = '#14213D', '#5A647A'
SHOW_MAX = 8.0   # seconds shown inside a phase
BEFORE = 10      # rows (1 s) shown before the phase

occ = {p: [] for p in ORDER}
for f in sorted(glob.glob(os.path.join(CLEANED_DIR, 'pill_good_*.csv'))):
    df = pd.read_csv(f)
    df = df[~df['action_label'].isin(['idle', 'searching_wall'])].reset_index(drop=True)
    seg = (df['action_label'] != df['action_label'].shift()).cumsum()
    for _, g in df.groupby(seg):
        ph = g['action_label'].iloc[0]
        if ph not in occ:
            continue
        i0, i1 = g.index[0], g.index[-1]
        occ[ph].append((df.loc[max(0, i0 - BEFORE):i0], df.loc[i0:i1]))

# fig, axes = plt.subplots(2, 5, figsize=(20, 8), sharey='row')
fig, axes = plt.subplots(4, 5, figsize=(20, 15), sharey='row')
for c, ph in enumerate(ORDER):
    for r, (col, ylab) in enumerate(SENSORS):
        ax = axes[r, c]
        longest = 0
        for before, inside in occ[ph]:
            tb = (np.arange(len(before)) - len(before) + 1) * 0.1
            ti = np.arange(len(inside)) * 0.1
            keep = ti <= SHOW_MAX
            ax.plot(tb, before[col].values, color='#B0B4BC', lw=1.2)
            ax.plot(np.r_[tb[-1:], ti[keep]], np.r_[before[col].values[-1:], inside[col].values[keep]],
                    color=COLORS[ph], lw=1.6, alpha=0.75)
            longest = max(longest, min(ti[-1], SHOW_MAX))
        ax.axvline(0, color=MUTED, ls='--', lw=1)
        ax.set_xlim(-1.05, longest + 0.1)
        if r == 0:
            n = len(occ[ph])
            ax.set_title(f'{ph.replace("_", " ")}\n({n} occurrences)', color=INK, fontsize=12)
        if c == 0:
            ax.set_ylabel(ylab, color=INK)
        # if r == 1:
        if r == 3:
            ax.set_xlabel('seconds from phase start')
        ax.grid(axis='y', color='#E4E6EA', lw=0.8)
        for sp in ['top', 'right']:
            ax.spines[sp].set_visible(False)
fig.suptitle('Each phase on its own: all good pillar runs on top of each other '
             '(grey = 1 s before the phase starts)', x=0.01, ha='left', color=INK, fontsize=13)
fig.tight_layout(rect=(0, 0, 1, 0.95))
fig.savefig('phase_panels.png', dpi=130)
print('Saved phase_panels.png')