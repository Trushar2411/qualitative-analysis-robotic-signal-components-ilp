#!/usr/bin/env python3
"""
trend_vs_jump.py  -  trend words vs jump words, drawn on ONE run's lidar_left

Inside every phase:   its TREND word (what QTA says about the whole phase)
At every phase start: the last 5 rows before (grey) and first 5 rows after (colour),
                      their averages (short flat lines) and an arrow = the JUMP word

HOW TO RUN (signal_processing folder, next to entry_features.py)
  ~/popper_env/bin/python trend_vs_jump.py
  RUN=pill_good_03 ~/popper_env/bin/python trend_vs_jump.py
Output: trend_vs_jump_<run>.png
"""
import os, glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from entry_features import apply_qta, CLEANED_DIR

RUN = os.environ.get('RUN', 'pill_good_01')
S = 'lidar_left'
COLORS = {'approaching_wall': '#2a78d6', 'wall_following': '#1baf7a',
          'obstacle_detected': '#e34948', 'obstacle_avoidance': '#eda100',
          'wall_reacquired': '#6250d6'}
INK, MUTED = '#14213D', '#5A647A'

f = sorted(glob.glob(os.path.join(CLEANED_DIR, f'{RUN}_*.csv')))[0]
df = pd.read_csv(f).reset_index(drop=True)
df['t'] = df.index * 0.1
segs = [g for _, g in df.groupby((df.action_label != df.action_label.shift()).cumsum())]

# zoom: from 2 s before obstacle_detected to 2 s after the first long wall_following after it
i_det = next(i for i, g in enumerate(segs) if g.action_label.iloc[0] == 'obstacle_detected')
i_end = next(i for i, g in enumerate(segs) if i > i_det and g.action_label.iloc[0] == 'wall_following' and len(g) > 20)
show = list(range(i_det - 1, i_end + 1))
a, b = segs[i_det].t.iloc[0] - 2.0, segs[i_end].t.iloc[0] + 2.0

fig, ax = plt.subplots(figsize=(16, 8.5))
z = df[(df.t >= a) & (df.t <= b)]
ax.plot(z.t, z[S], color='#8A90A0', lw=1.5, zorder=2)

print(f'{RUN}  lidar_left')
print(f'{"phase":<20}{"trend":>12}{"before":>9}{"after":>9}{"jump":>8}  word')
for k, i in enumerate(show):
    g = segs[i]; ph = g.action_label.iloc[0]
    if ph not in COLORS:
        continue
    t0, t1 = max(g.t.iloc[0], a), min(g.t.iloc[-1] + 0.1, b)
    ax.axvspan(t0, t1, color=COLORS[ph], alpha=0.13, lw=0, zorder=0)
    inside = g[(g.t >= a) & (g.t <= b)]
    ax.plot(inside.t, inside[S], color=COLORS[ph], lw=2.6, zorder=3)
    trend = apply_qta(g[S].values).replace('is_', '')
    long = (t1 - t0) > 0.9
    ax.text((t0 + t1) / 2, 1.02 + (0 if long or k % 2 else 0.11), ph.replace('_', '\n'), transform=ax.get_xaxis_transform(),
            ha='center', va='bottom', fontsize=10, fontweight='bold', color=COLORS[ph])
    ax.text((t0 + t1) / 2, 0.02 + (0 if long or k % 2 else 0.08), f'trend:\n{trend}', transform=ax.get_xaxis_transform(),
            ha='center', va='bottom', fontsize=10, color=INK,
            bbox=dict(boxstyle='round,pad=0.3', fc='white', ec=COLORS[ph], lw=1.5))
    if i == show[0] or i == 0:
        continue
    prev = segs[i - 1]
    pb, pa = prev.tail(5), g.head(5)
    mb, ma = pb[S].mean(), pa[S].mean()
    jump = ma - mb
    word = 'jump UP' if jump > 0.10 else 'jump DOWN' if jump < -0.10 else 'no jump'
    print(f'{ph:<20}{trend:>12}{mb:>9.2f}{ma:>9.2f}{jump:>+8.2f}  {word}')
    ax.plot(pb.t, pb[S], color=INK, lw=5, alpha=0.35, solid_capstyle='butt', zorder=4)
    ax.plot(pa.t, pa[S], color=COLORS[ph], lw=6, alpha=0.6, solid_capstyle='butt', zorder=4)
    ax.hlines(mb, pb.t.iloc[0], pb.t.iloc[-1], color=INK, lw=2.5, zorder=5)
    ax.hlines(ma, pa.t.iloc[0], pa.t.iloc[-1], color=COLORS[ph], lw=2.5, zorder=5)
    xm = g.t.iloc[0] - 0.05
    if abs(jump) > 0.10:
        ax.annotate('', xy=(xm, ma), xytext=(xm, mb),
                    arrowprops=dict(arrowstyle='-|>', color='#C0392B', lw=2.5, mutation_scale=18), zorder=6)
        ax.text(xm - 0.08, (ma + mb) / 2, f'{word}\n{mb:.2f} → {ma:.2f}', ha='right', va='center',
                fontsize=11, fontweight='bold', color='#C0392B', zorder=6,
                bbox=dict(boxstyle='round,pad=0.25', fc='white', ec='none', alpha=0.85))
    else:
        ax.text(xm, max(ma, mb) + 0.06, f'no jump\n{mb:.2f} → {ma:.2f}', ha='center', va='bottom',
                fontsize=9, color=MUTED, zorder=6)

ax.set_xlim(a, b)
ax.set_ylim(z[S].min() - 0.28, z[S].max() + 0.05)
ax.set_xlabel('time since run start (s)')
ax.set_ylabel('lidar_left (m)')
for sp in ['top', 'right']:
    ax.spines[sp].set_visible(False)
ax.grid(axis='y', color='#E4E6EA', lw=0.8)
ax.set_title(f'{RUN}: TREND word = what happens inside a phase (boxes at the bottom)   ·   '
             f'JUMP word = average of 5 rows after − 5 rows before a phase starts (arrows)',
             loc='left', fontsize=11.5, color=INK, pad=100)
fig.subplots_adjust(top=0.82, bottom=0.08, left=0.06, right=0.98)
out = f'trend_vs_jump_{RUN}.png'
fig.savefig(out, dpi=140)
print('Saved', out)