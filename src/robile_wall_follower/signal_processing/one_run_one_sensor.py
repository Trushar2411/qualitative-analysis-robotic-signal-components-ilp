#!/usr/bin/env python3
"""
one_run_one_sensor.py  -  ONE run, ONE sensor, phases marked

Figure 1 (top):    the whole run, background coloured by phase
Figure 2 (bottom): zoom on the pillar part; every phase is named, its value at
                   the START (o) is written on the plot, and the value just
                   before a jump (x)

HOW TO RUN (in the signal_processing folder)
  ~/popper_env/bin/python one_run_one_sensor.py                      # pill_good_01, lidar_left
  RUN=pill_good_03 ~/popper_env/bin/python one_run_one_sensor.py
  SENSOR=lidar_right ~/popper_env/bin/python one_run_one_sensor.py   # later: other sensors
Output: one_run_plots/<run>_<sensor>.png
"""
import os, glob
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

CLEANED_DIR = os.path.expanduser('~/rnd_ws/data_cleaned')
RUN = os.environ.get('RUN', 'pill_good_01')
SENSOR = os.environ.get('SENSOR', 'lidar_left')
OUT = 'one_run_plots'
COLORS = {'approaching_wall': '#2a78d6', 'wall_following': '#1baf7a',
          'obstacle_detected': '#e34948', 'obstacle_avoidance': '#eda100',
          'wall_reacquired': '#6250d6'}
OTHER, INK, MUTED = '#DDDDDD', '#14213D', '#5A647A'

f = sorted(glob.glob(os.path.join(CLEANED_DIR, f'{RUN}_*.csv')))[0]
df = pd.read_csv(f).reset_index(drop=True)
df['t'] = df.index * 0.1                                   # 10 rows per second
seg = (df['action_label'] != df['action_label'].shift()).cumsum()
segs = [g for _, g in df.groupby(seg)]

# print every phase with its start / end value
print(f'{RUN}  {SENSOR}')
print(f'{"phase":<20}{"from s":>8}{"to s":>8}{"start":>8}{"end":>8}')
for g in segs:
    print(f'{g.action_label.iloc[0]:<20}{g.t.iloc[0]:>8.1f}{g.t.iloc[-1]:>8.1f}'
          f'{g[SENSOR].iloc[0]:>8.2f}{g[SENSOR].iloc[-1]:>8.2f}')

# zoom window: 2 s before obstacle_detected until 2 s after the next wall_following starts
det = [g for g in segs if g.action_label.iloc[0] == 'obstacle_detected']
if det:
    a = det[0].t.iloc[0] - 2
    nxt = [g for g in segs if g.action_label.iloc[0] == 'wall_following' and g.t.iloc[0] > a + 2]
    b = nxt[0].t.iloc[0] + 2 if nxt else df.t.iloc[-1]
else:
    a, b = df.t.iloc[0], df.t.iloc[-1]

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), gridspec_kw={'height_ratios': [1, 1.3]})


def shade(ax, lo, hi, names):
    k = 0
    for i, g in enumerate(segs):
        t0, t1 = g.t.iloc[0], g.t.iloc[-1] + 0.1
        if t1 < lo or t0 > hi:
            continue
        ph = g.action_label.iloc[0]
        ax.axvspan(max(t0, lo), min(t1, hi), color=COLORS.get(ph, OTHER), alpha=0.2, lw=0)
        if not names or ph not in COLORS:
            continue
        # phase name above the plot, two heights so short phases don't overlap
        ax.text((max(t0, lo) + min(t1, hi)) / 2, 1.01 + 0.09 * (k % 2), ph.replace('_', '\n'),
                transform=ax.get_xaxis_transform(), ha='center', va='bottom', fontsize=9,
                color=COLORS[ph], fontweight='bold')
        k += 1
        # o = value at phase start (only if inside the zoom)
        if lo <= g.t.iloc[0] <= hi:
            v0 = g[SENSOR].iloc[0]
            ax.plot(g.t.iloc[0], v0, 'o', color=COLORS[ph], ms=8)
            ax.annotate(f'{v0:.2f}', (g.t.iloc[0], v0), textcoords='offset points',
                        xytext=(6, 6), fontsize=10, color=INK, fontweight='bold')
        # x = value at phase end, only if it differs from the next start (= a jump)
        if lo <= g.t.iloc[-1] <= hi and i + 1 < len(segs):
            v1, nxt = g[SENSOR].iloc[-1], segs[i + 1][SENSOR].iloc[0]
            if abs(nxt - v1) >= 0.05:
                ax.plot(g.t.iloc[-1], v1, 'x', color=COLORS[ph], ms=8, mew=2)
                ax.annotate(f'{v1:.2f}', (g.t.iloc[-1], v1), textcoords='offset points',
                            xytext=(-34, -4), fontsize=10, color=INK)


for ax in (ax1, ax2):
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    ax.grid(axis='y', color='#E4E6EA', lw=0.8)
    ax.set_ylabel(f'{SENSOR} (m)')

shade(ax1, df.t.iloc[0], df.t.iloc[-1], names=False)
ax1.plot(df.t, df[SENSOR], color=INK, lw=1.6)
ax1.axvspan(a, b, fill=False, ec=MUTED, ls='--', lw=1.2)
ax1.set_title(f'{RUN}: {SENSOR} over the whole run (dashed box = zoom below)', loc='left', color=INK)

z = df[(df.t >= a) & (df.t <= b)]
shade(ax2, a, b, names=True)
ax2.plot(z.t, z[SENSOR], color=INK, lw=2)
ax2.set_xlabel('time since run start (s)')
ax2.set_xlim(a, b)
ax2.set_title(f'Zoom on the pillar part   (o = value at phase start, x = value just before a jump)',
              loc='left', color=INK, pad=60)

fig.legend(handles=[Patch(color=c, alpha=0.4, label=p) for p, c in COLORS.items()] +
           [Patch(color=OTHER, alpha=0.6, label='other (idle, searching_wall)')],
           loc='lower center', ncol=6, frameon=False, fontsize=10)
fig.subplots_adjust(bottom=0.09, hspace=0.45, top=0.95)
os.makedirs(OUT, exist_ok=True)
out = f'{OUT}/{RUN}_{SENSOR}.png'
fig.savefig(out, dpi=140)
print('Saved', out)