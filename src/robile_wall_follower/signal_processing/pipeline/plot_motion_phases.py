#!/usr/bin/env python3
"""
plot_motion_phases.py  -  do the robot's own motion sensors show the phases?

Same layout as phase_panels.png: one column per phase, all good pillar runs on top
of each other, grey = 1 s before the phase starts. Rows:
  speed_from_distance  forward speed from odometry = change of distance_travelled per second
                       (smoothed over 5 rows)
  odom_angular_z       turning speed from odometry (the robot is not supposed to turn)
  imu_angular_z        turning speed from the IMU
  imu_accel_y          sideways acceleration
  imu_accel_x          forward acceleration
Output: ~/rnd_ws/phase_plots/motion_sensor_panels.png
"""
import os, glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CLEANED_DIR = os.path.expanduser('~/rnd_ws/data_cleaned')
OUT = os.path.expanduser('~/rnd_ws/phase_plots/motion_sensor_panels.png')
ORDER = ['wall_following', 'obstacle_detected', 'obstacle_avoidance', 'wall_reacquired', 'approaching_wall']
COLORS = dict(zip(['approaching_wall', 'wall_following', 'obstacle_detected', 'obstacle_avoidance', 'wall_reacquired'],
                  ['#2a78d6', '#1baf7a', '#e34948', '#eda100', '#6250d6']))
SENSORS = [('speed_from_distance', 'forward speed (m/s)\nfrom distance_travelled'),
           ('odom_angular_z', 'odom_angular_z\nturning (odometry)'),
           ('imu_angular_z', 'imu_angular_z\nturning (IMU)'),
           ('imu_accel_y', 'imu_accel_y\nsideways accel.'),
           ('imu_accel_x', 'imu_accel_x\nforward accel.')]
INK, MUTED = '#14213D', '#5A647A'
SHOW_MAX, BEFORE = 8.0, 10

occ = {p: [] for p in ORDER}
for f in sorted(glob.glob(os.path.join(CLEANED_DIR, 'pill_good_*.csv'))):
    df = pd.read_csv(f).reset_index(drop=True)
    df['speed_from_distance'] = (df['distance_travelled'].diff() * 10).rolling(5, center=True, min_periods=1).mean()
    df = df[~df['action_label'].isin(['idle', 'searching_wall'])].reset_index(drop=True)
    seg = (df['action_label'] != df['action_label'].shift()).cumsum()
    for _, g in df.groupby(seg):
        ph = g['action_label'].iloc[0]
        if ph in occ:
            i0, i1 = g.index[0], g.index[-1]
            occ[ph].append((df.loc[max(0, i0 - BEFORE):i0], df.loc[i0:i1]))

fig, axes = plt.subplots(len(SENSORS), 5, figsize=(20, 3.6 * len(SENSORS)), sharey='row')
for c, ph in enumerate(ORDER):
    for r, (col, ylab) in enumerate(SENSORS):
        ax = axes[r, c]
        longest = 0
        for before, inside in occ[ph]:
            if col not in inside.columns:
                continue
            tb = (np.arange(len(before)) - len(before) + 1) * 0.1
            ti = np.arange(len(inside)) * 0.1
            keep = ti <= SHOW_MAX
            ax.plot(tb, before[col].values, color='#B0B4BC', lw=1.1)
            ax.plot(np.r_[tb[-1:], ti[keep]], np.r_[before[col].values[-1:], inside[col].values[keep]],
                    color=COLORS[ph], lw=1.4, alpha=0.75)
            longest = max(longest, min(ti[-1], SHOW_MAX))
        ax.axvline(0, color=MUTED, ls='--', lw=1)
        ax.axhline(0, color='#D9DCE1', lw=0.8)
        ax.set_xlim(-1.05, longest + 0.1)
        if r == 0:
            ax.set_title(f'{ph.replace("_", " ")}\n({len(occ[ph])} occurrences)', color=INK, fontsize=12)
        if c == 0:
            ax.set_ylabel(ylab, color=INK)
        if r == len(SENSORS) - 1:
            ax.set_xlabel('seconds from phase start')
        for sp in ['top', 'right']:
            ax.spines[sp].set_visible(False)
fig.suptitle("Robot's own motion sensors per phase: all good pillar runs on top of each other (grey = 1 s before)",
             x=0.01, ha='left', color=INK, fontsize=13)
fig.tight_layout(rect=(0, 0, 1, 0.96))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
fig.savefig(OUT, dpi=120)
print('Saved', OUT)