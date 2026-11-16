#!/usr/bin/env python3
"""
add_odometry.py  -  bring odometry back into the cleaned runs and turn it into
                    the robot's own FORWARD and SIDEWAYS speed

For every cleaned run in ~/rnd_ws/data_cleaned:
  1. find the raw file whose time range contains the run (same idea as fix_lidar_range.py)
  2. copy pos_x, pos_y and odom_angular_z (odometry) into the run, matched by timestamp
  3. odometry x/y are in the odometry frame, not the robot's frame. The robot may also turn a little
     during the run, so its heading is followed row by row: heading = start heading + odometry
     turning rate (odom_angular_z) x time. The start heading is chosen so that the measured motion
     in a REFERENCE phase points the way the autopilot commanded it:
        obstacle_avoidance : forward 0.08 m/s, sideways -0.35 m/s (slide right)   (pillar runs)
        searching_wall     : forward 0,        sideways +0.2 m/s  (slide left)    (if no avoidance)
        wall_following     : forward only                                         (last resort)
     Only the DIRECTION of the command is used, once per run; all speeds are measured.
  4. forward_speed (+ = forward) and side_speed (+ = LEFT, toward the wall), per second,
     smoothed over 5 rows; impossible values (> 1 m/s, odometry resets) removed
  5. columns added: pos_x_odom, pos_y_odom, turn_rate_odom, heading_change_deg, forward_speed, side_speed
  6. self-check: median measured speed per phase vs the autopilot's command
The original data_cleaned files are NOT changed. Results go to ~/rnd_ws/data_cleaned_odom/
and a check plot to ~/rnd_ws/phase_plots/odometry_speed_panels.png

HOW TO RUN (signal_processing folder)
  ~/popper_env/bin/python add_odometry.py
"""
import os, glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CLEANED_DIR = os.path.expanduser('~/rnd_ws/data_cleaned')
RAW_DIRS = [os.path.expanduser('~/rnd_ws/data'), os.path.expanduser('~/rnd_ws/data_pillar')]
OUT_DIR = os.path.expanduser('~/rnd_ws/data_cleaned_odom')
PLOT = os.path.expanduser('~/rnd_ws/phase_plots/odometry_speed_panels.png')
# autopilot commands (pillar_follower_node.py, FORWARD_SPEED = 0.1, AVOIDANCE_OFFSET = 0.35)
COMMAND = {'obstacle_detected': (0.05, 0.0), 'obstacle_avoidance': (0.08, -0.35),
           'wall_reacquired': (0.08, 0.245), 'searching_wall': (0.0, 0.2),
           'approaching_wall': (0.1, None), 'wall_following': (0.1, None)}


def to_time(s):
    return pd.to_datetime(s, errors='coerce')


def load_raws():
    raws = []
    for d in RAW_DIRS:
        for f in sorted(glob.glob(os.path.join(d, '*.csv'))):
            df = pd.read_csv(f)
            if not {'timestamp', 'pos_x', 'pos_y', 'odom_angular_z'} <= set(df.columns):
                continue
            df['_t'] = to_time(df['timestamp'])
            raws.append((f, df.dropna(subset=['_t']).sort_values('_t')))
    return raws


def find_raw(t_mid, raws):
    for f, df in raws:
        if df['_t'].min() <= t_mid <= df['_t'].max():
            return f, df
    return None, None


def reference_rows(df):
    """rows (steady part of a phase) + commanded direction (forward, sideways) in the robot frame"""
    lab = df['action_label']
    k = lab.groupby((lab != lab.shift()).cumsum()).cumcount()          # row number inside each phase piece
    for ph in ['obstacle_avoidance', 'searching_wall']:
        rows = (lab == ph) & (k >= 10)                                  # skip the first 1 s (speeding up)
        if rows.sum() >= 5:
            return ph, rows, COMMAND[ph]
    return 'wall_following', (lab == 'wall_following') & (k >= 10), (1.0, 0.0)


def speeds(df):
    dx = df['pos_x_odom'].diff()
    dy = df['pos_y_odom'].diff()
    bad = np.hypot(dx, dy) * 10 > 1.0                                   # > 1 m/s = odometry jump
    dx[bad], dy[bad] = np.nan, np.nan
    # how much the robot has turned since the start of the run (odometry turning rate x time)
    dt = to_time(df['timestamp']).diff().dt.total_seconds().fillna(0).clip(0, 0.5)
    psi = (df['turn_rate_odom'].fillna(0) * dt).cumsum()
    # movement with that turning taken out
    ux = dx * np.cos(psi) + dy * np.sin(psi)
    uy = -dx * np.sin(psi) + dy * np.cos(psi)
    ref, rows, (cf, cs) = reference_rows(df)
    theta0 = np.arctan2(uy[rows].sum(), ux[rows].sum()) - np.arctan2(cs, cf)   # heading at the start
    fwd = (ux * np.cos(theta0) + uy * np.sin(theta0)) * 10
    side = (-ux * np.sin(theta0) + uy * np.cos(theta0)) * 10
    df['forward_speed'] = fwd.rolling(5, center=True, min_periods=1).mean().round(4)
    df['side_speed'] = side.rolling(5, center=True, min_periods=1).mean().round(4)
    df['heading_change_deg'] = np.degrees(psi).round(2)
    return ref, np.degrees(theta0), np.degrees(psi.max() - psi.min())


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    raws = load_raws()
    print(f'{len(raws)} raw files with pos_x/pos_y/odom_angular_z found\n')
    print(f'{"cleaned run":<40}{"raw file":<40}{"matched":>8}  {"reference":<20}{"start":>6}{"turned":>8}')
    for f in sorted(glob.glob(os.path.join(CLEANED_DIR, '*.csv'))):
        df = pd.read_csv(f)
        t = to_time(df['timestamp'])
        raw_f, raw = find_raw(t.iloc[len(t) // 2], raws)
        name = os.path.basename(f)
        if raw is None:
            print(f'{name:<40}{"NOT FOUND":<40}')
            df.to_csv(os.path.join(OUT_DIR, name), index=False)
            continue
        left = pd.DataFrame({'_t': t, '_i': range(len(df))}).dropna().sort_values('_t')
        m = pd.merge_asof(left, raw[['_t', 'pos_x', 'pos_y', 'odom_angular_z']].rename(
                              columns={'pos_x': 'pos_x_odom', 'pos_y': 'pos_y_odom', 'odom_angular_z': 'turn_rate_odom'}),
                          on='_t', direction='nearest', tolerance=pd.Timedelta('60ms')).sort_values('_i')
        for c in ['pos_x_odom', 'pos_y_odom', 'turn_rate_odom']:
            df[c] = m[c].values
        matched = 100 * df['pos_x_odom'].notna().mean()
        ref, start, turned = speeds(df)
        df.to_csv(os.path.join(OUT_DIR, name), index=False)
        print(f'{name:<40}{os.path.basename(raw_f):<40}{matched:>7.0f}%  {ref:<20}{start:>5.0f}°{turned:>7.0f}°')
    print(f'\nSaved cleaned runs + forward_speed + side_speed in {OUT_DIR}')
    print('start = heading at the start of the run in the odometry frame; turned = how much the robot turned during the run')
    check()
    plot()


def check():
    rows = []
    for f in sorted(glob.glob(os.path.join(OUT_DIR, '*_good_*.csv'))):
        df = pd.read_csv(f)
        if 'side_speed' not in df:
            continue
        piece = (df.action_label != df.action_label.shift()).cumsum()
        k = df.groupby(piece).cumcount()
        n = df.groupby(piece)['action_label'].transform('size')
        steady = df[(k >= 10) | (n < 15)]                                # skip the first 1 s, keep short phases whole
        for ph, g in steady.groupby('action_label'):
            rows.append(dict(task='pillar' if 'pill' in f else 'plain', phase=ph,
                             forward=g.forward_speed.median(), side=g.side_speed.median()))
    t = pd.DataFrame(rows).groupby(['task', 'phase'])[['forward', 'side']].median().round(3)
    t['cmd_forward'] = [COMMAND.get(p, (None, None))[0] for _, p in t.index]
    t['cmd_side'] = [COMMAND.get(p, (None, None))[1] for _, p in t.index]
    print('\nSELF-CHECK: median measured speed (m/s) vs command')
    print('(NaN in cmd_side = sideways is a correction that changes all the time)')
    print(t.to_string())


def plot():
    order = ['wall_following', 'obstacle_detected', 'obstacle_avoidance', 'wall_reacquired', 'approaching_wall']
    colors = dict(zip(['approaching_wall', 'wall_following', 'obstacle_detected', 'obstacle_avoidance', 'wall_reacquired'],
                      ['#2a78d6', '#1baf7a', '#e34948', '#eda100', '#6250d6']))
    rows = [('side_speed', 'side_speed (m/s)\n+ = left, toward wall'), ('forward_speed', 'forward_speed (m/s)'),
            ('heading_change_deg', 'heading change since\nrun start (deg)')]
    occ = {p: [] for p in order}
    for f in sorted(glob.glob(os.path.join(OUT_DIR, 'pill_good_*.csv'))):
        df = pd.read_csv(f)
        if 'side_speed' not in df:
            continue
        df = df[~df['action_label'].isin(['idle', 'searching_wall'])].reset_index(drop=True)
        seg = (df['action_label'] != df['action_label'].shift()).cumsum()
        for _, g in df.groupby(seg):
            ph = g['action_label'].iloc[0]
            if ph in occ:
                i0, i1 = g.index[0], g.index[-1]
                occ[ph].append((df.loc[max(0, i0 - 10):i0], df.loc[i0:i1]))
    fig, axes = plt.subplots(len(rows), 5, figsize=(20, 3.7 * len(rows)), sharey='row')
    for c, ph in enumerate(order):
        for r, (col, lab) in enumerate(rows):
            ax = axes[r, c]
            longest = 0
            for before, inside in occ[ph]:
                tb = (np.arange(len(before)) - len(before) + 1) * 0.1
                ti = np.arange(len(inside)) * 0.1
                keep = ti <= 8
                ax.plot(tb, before[col].values, color='#B0B4BC', lw=1.1)
                ax.plot(np.r_[tb[-1:], ti[keep]], np.r_[before[col].values[-1:], inside[col].values[keep]],
                        color=colors[ph], lw=1.5, alpha=0.8)
                longest = max(longest, min(ti[-1], 8))
            ax.axvline(0, color='#5A647A', ls='--', lw=1)
            ax.axhline(0, color='#D9DCE1', lw=0.8)
            ax.set_xlim(-1.05, longest + 0.1)
            if r == 0:
                ax.set_title(f'{ph.replace("_", " ")}\n({len(occ[ph])} occurrences)', fontsize=12)
            if c == 0:
                ax.set_ylabel(lab)
            if r == len(rows) - 1:
                ax.set_xlabel('seconds from phase start')
            for sp in ['top', 'right']:
                ax.spines[sp].set_visible(False)
    fig.suptitle('Odometry speeds in the robot\'s own frame, all good pillar runs (grey = 1 s before)', x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    os.makedirs(os.path.dirname(PLOT), exist_ok=True)
    fig.savefig(PLOT, dpi=120)
    print('\nSaved plot', PLOT)


if __name__ == '__main__':
    main()