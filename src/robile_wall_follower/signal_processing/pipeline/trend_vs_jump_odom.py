#!/usr/bin/env python3
"""
trend_vs_jump_odom.py  -  trend words vs jump words for the ODOMETRY signals of ONE run
                          (side_speed and turn_rate_odom, as used by ilp_multisensor.py)

For side_speed (+ = moving left, toward the wall) and turn_rate_odom (twisting), plus lidar_left for comparison:
  boxes at the bottom = TREND word inside each phase (QTA; for odometry with limits relative to the
                        signal's range, exactly as in ilp_multisensor.py)
  red arrows          = JUMP word at each phase start (5 rows after - 5 rows before;
                        limit 10 cm for the lidar, 10 % of the range for odometry)
Everything is saved in ONE folder:
  ~/rnd_ws/phase_plots/<run>/odom_<run>_<sensor>.png   one picture per signal
  ~/rnd_ws/phase_plots/<run>/odom_<run>_all.pdf         all pictures, one per page
  ~/rnd_ws/phase_plots/<run>/odom_<run>_words.csv       the table of trend + jump words

HOW TO RUN (pipeline folder, next to entry_features.py and ilp_multisensor.py)
  ~/popper_env/bin/python trend_vs_jump_odom.py
  RUN=pill_good_03 ~/popper_env/bin/python trend_vs_jump_odom.py
"""
import os, glob
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from entry_features import apply_qta
import ilp_multisensor as M

RUN = os.environ.get('RUN', 'pill_good_01')
SENSORS = ['side_speed', 'turn_rate_odom', 'lidar_left']
SC = M.scales(M.load_runs())                        # same scales as ilp_multisensor.py
UNIT = {'side_speed': 'm/s, + = left', 'turn_rate_odom': 'rad/s', 'lidar_left': 'm'}
OUT = os.path.expanduser(f'~/rnd_ws/phase_plots/{RUN}')
JUMP = 0.10
COLORS = {'approaching_wall': '#2a78d6', 'wall_following': '#1baf7a',
          'obstacle_detected': '#e34948', 'obstacle_avoidance': '#eda100',
          'wall_reacquired': '#6250d6'}
INK, MUTED = '#14213D', '#5A647A'

f = sorted(glob.glob(os.path.join(M.DATA_DIR, f'{RUN}_*.csv')))[0]
df = pd.read_csv(f).reset_index(drop=True)
df['t'] = df.index * 0.1
segs = [g for _, g in df.groupby((df.action_label != df.action_label.shift()).cumsum())]
i_det = next(i for i, g in enumerate(segs) if g.action_label.iloc[0] == 'obstacle_detected')
i_end = next(i for i, g in enumerate(segs) if i > i_det and g.action_label.iloc[0] == 'wall_following' and len(g) > 20)
show = list(range(i_det - 1, i_end + 1))
a, b = segs[i_det].t.iloc[0] - 2.0, segs[i_end].t.iloc[0] + 2.0
z = df[(df.t >= a) & (df.t <= b)]


def plot_sensor(S, rows):
    fig, ax = plt.subplots(figsize=(16, 8.5))
    lo, hi = z[S].min(), z[S].max()
    span = max(hi - lo, 0.3 if S not in SC else 1e-6)
    fm = '.3f' if S in SC else '.2f'
    ax.plot(z.t, z[S], color='#8A90A0', lw=1.5, zorder=2)
    for k, i in enumerate(show):
        g = segs[i]; ph = g.action_label.iloc[0]
        if ph not in COLORS:
            continue
        t0, t1 = max(g.t.iloc[0], a), min(g.t.iloc[-1] + 0.1, b)
        ax.axvspan(t0, t1, color=COLORS[ph], alpha=0.13, lw=0, zorder=0)
        inside = g[(g.t >= a) & (g.t <= b)]
        ax.plot(inside.t, inside[S], color=COLORS[ph], lw=2.6, zorder=3)
        trend = M.qta_scaled(g[S].values, SC[S]) if S in SC else apply_qta(g[S].values).replace('is_', '')
        long = (t1 - t0) > 0.9
        ax.text((t0 + t1) / 2, 1.02 + (0 if long or k % 2 else 0.11), ph.replace('_', '\n'),
                transform=ax.get_xaxis_transform(), ha='center', va='bottom', fontsize=10,
                fontweight='bold', color=COLORS[ph])
        ax.text((t0 + t1) / 2, 0.02 + (0 if long or k % 2 else 0.08), f'trend:\n{trend}',
                transform=ax.get_xaxis_transform(), ha='center', va='bottom', fontsize=10, color=INK,
                bbox=dict(boxstyle='round,pad=0.3', fc='white', ec=COLORS[ph], lw=1.5))
        if i == show[0] or i == 0:
            continue
        pb, pa = segs[i - 1].tail(5), g.head(5)
        mb, ma = pb[S].mean(), pa[S].mean()
        jump = ma - mb
        lim = 0.10 * SC[S] if S in SC else JUMP
        word = 'jump UP' if jump > lim else 'jump DOWN' if jump < -lim else 'no jump'
        rows.append(dict(sensor=S, phase=ph, start_s=round(g.t.iloc[0], 1), trend=trend, limit=round(lim, 3),
                         before=round(mb, 3), after=round(ma, 3), jump=round(jump, 3), jump_word=word))
        ax.plot(pb.t, pb[S], color=INK, lw=5, alpha=0.35, solid_capstyle='butt', zorder=4)
        ax.plot(pa.t, pa[S], color=COLORS[ph], lw=6, alpha=0.6, solid_capstyle='butt', zorder=4)
        ax.hlines(mb, pb.t.iloc[0], pb.t.iloc[-1], color=INK, lw=2.5, zorder=5)
        ax.hlines(ma, pa.t.iloc[0], pa.t.iloc[-1], color=COLORS[ph], lw=2.5, zorder=5)
        xm = g.t.iloc[0] - 0.05
        if abs(jump) > lim:
            ax.annotate('', xy=(xm, ma), xytext=(xm, mb),
                        arrowprops=dict(arrowstyle='-|>', color='#C0392B', lw=2.5, mutation_scale=18), zorder=6)
            ax.text(xm - 0.08, (ma + mb) / 2, f'{word}\n{mb:{fm}} → {ma:{fm}}', ha='right', va='center',
                    fontsize=11, fontweight='bold', color='#C0392B', zorder=6,
                    bbox=dict(boxstyle='round,pad=0.25', fc='white', ec='none', alpha=0.85))
        else:
            ax.text(xm, max(ma, mb) + 0.04 * span, f'no jump\n{mb:{fm}} → {ma:{fm}}', ha='center',
                    va='bottom', fontsize=9, color=MUTED, zorder=6)
    ax.axhline(0, color='#D9DCE1', lw=0.8)
    if hi >= 9.9:
        ax.axhline(10, color=MUTED, ls='--', lw=1)
        ax.text(a + 0.1, 10 + 0.02 * span, '10 m = no return (lidar saw nothing, capped)',
                fontsize=10, color=MUTED, va='bottom')
    ax.set_xlim(a, b)
    ax.set_ylim(lo - 0.3 * span, hi + 0.08 * span)
    ax.set_xlabel('time since run start (s)')
    ax.set_ylabel(f'{S} ({UNIT[S]})')
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    ax.grid(axis='y', color='#E4E6EA', lw=0.8)
    ax.set_title(f'{RUN} · {S}:  TREND word = inside a phase (boxes)  ·  '
                 f'JUMP word = 5 rows after − 5 rows before a phase starts (arrows)',
                 loc='left', fontsize=11.5, color=INK, pad=100)
    fig.subplots_adjust(top=0.80, bottom=0.08, left=0.06, right=0.98)
    return fig


os.makedirs(OUT, exist_ok=True)
rows = []
pdf_path = f'{OUT}/odom_{RUN}_all.pdf'
with PdfPages(pdf_path) as pdf:
    for S in SENSORS:
        fig = plot_sensor(S, rows)
        fig.savefig(f'{OUT}/odom_{RUN}_{S}.png', dpi=140)
        pdf.savefig(fig)
        plt.close(fig)

t = pd.DataFrame(rows)
t.to_csv(f'{OUT}/odom_{RUN}_words.csv', index=False)
pd.set_option('display.width', 200)
for S in SENSORS:
    print(f'\n=== {S}  (jump limit {0.1 * SC[S]:.3f}) ===' if S in SC else f'\n=== {S}  (jump limit 0.10) ===')
    print(t[t.sensor == S].drop(columns='sensor').to_string(index=False))
print(f'\nAll saved in: {OUT}')
for n in sorted(os.listdir(OUT)):
    print('  ', n)