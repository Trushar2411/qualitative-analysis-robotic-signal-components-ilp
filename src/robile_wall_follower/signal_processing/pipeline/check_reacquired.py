#!/usr/bin/env python3
"""
check_reacquired.py  -  is "lidar_left constant in wall_reacquired" real, or a summary effect?

For every wall_reacquired phase in the 7 good pillar runs it prints:
  before   = mean lidar_left, last 5 rows of the previous phase (avoidance)
  start    = mean of the first 5 rows of wall_reacquired
  end      = mean of the last 5 rows of wall_reacquired
  jump     = start - before   (entry word)
  inside   = end - start      (negative = robot moving back toward the wall)
  cv, slope = the two numbers QTA uses; qta = QTA word for the whole phase
  qta_no_jump = QTA word if the first 5 rows (the jump) are left out
and saves reacquired_check.png: lidar_left around every wall_reacquired phase.
"""
import os, glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from entry_features import segments, apply_qta, CLEANED_DIR

rows, curves = [], []
for f in sorted(glob.glob(os.path.join(CLEANED_DIR, 'pill_good_*.csv'))):
    run = '_'.join(os.path.basename(f).split('_')[:3])
    df = pd.read_csv(f).reset_index(drop=True)
    for s in segments(df):
        if s['phase'] != 'wall_reacquired' or s['prev'] is None:
            continue
        v = s['seg']['lidar_left'].values.astype(float)
        before = np.nanmean(s['prev']['lidar_left'].values[-5:])
        start, end = np.nanmean(v[:5]), np.nanmean(v[-5:])
        m = np.nanmean(v)
        slope = np.polyfit(np.arange(len(v)), v, 1)[0] / abs(m)
        rows.append(dict(run=run, rows=len(v), before=before, start=start, end=end,
                         jump=start - before, inside=end - start,
                         cv=np.nanstd(v) / abs(m), slope=slope,
                         qta=apply_qta(v).replace('is_', ''),
                         qta_no_jump=apply_qta(v[5:]).replace('is_', '')))
        i0 = s['seg'].index[0]
        win = df.loc[max(0, i0 - 30): i0 + len(v) + 15, 'lidar_left'].values
        curves.append((run, (np.arange(len(win)) - min(30, i0)) / 10, win, len(v) / 10))

t = pd.DataFrame(rows)
pd.set_option('display.width', 200)
print(t.round(3).to_string(index=False))
print('\nQTA limits: constant if cv < 0.05; increasing/decreasing if |slope| > 0.005')

fig, ax = plt.subplots(figsize=(12, 5))
ax.axvspan(0, max(c[3] for c in curves), color='#6250d6', alpha=0.15, lw=0)
ax.text(0.05, 0.97, 'wall_reacquired (1.5 s)', transform=ax.get_xaxis_transform(), va='top', color='#14213D')
ax.text(-2.9, 0.97, 'obstacle_avoidance', transform=ax.get_xaxis_transform(), va='top', color='#14213D')
for run, x, y, _ in curves:
    ax.plot(x, y, lw=1.8, label=run)
ax.axvline(0, color='#5A647A', ls='--', lw=1)
ax.set_xlabel('time from start of wall_reacquired (s)')
ax.set_ylabel('lidar_left (m)')
ax.set_title('lidar_left around every wall_reacquired phase (good pillar runs)', loc='left')
ax.legend(frameon=False, fontsize=9, ncol=4, loc='lower right')
for sp in ['top', 'right']:
    ax.spines[sp].set_visible(False)
fig.tight_layout()
fig.savefig('reacquired_check.png', dpi=150)
print('Saved reacquired_check.png')
