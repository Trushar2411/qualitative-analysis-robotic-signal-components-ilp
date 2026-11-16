#!/usr/bin/env python3
"""
screen_signals.py  -  which recorded signals could help describe the phases?

Part 1  report card for every numeric signal in the cleaned good runs:
        in how many runs it exists, missing %, exactly-zero %, number of different values, min / max
Part 2  phase score (0 = no help, 1 = separates the phases perfectly) for 3 numbers per phase piece:
          mean   = average inside the phase
          change = end - start (mean of last 5 rows - mean of first 5 rows)
          jump   = start of phase - end of previous phase (5 rows each, like jump words)
        score = share of the variation explained by the phase (eta squared)
Part 3  other CSV folders under ~/rnd_ws and their columns (signals we may not have used)

Saved to ~/rnd_ws/phase_plots/signal_screening.csv
"""
import os, glob
import numpy as np
import pandas as pd

CLEANED_DIR = os.path.expanduser('~/rnd_ws/data_cleaned')
PHASES = ['approaching_wall', 'wall_following', 'obstacle_detected', 'obstacle_avoidance', 'wall_reacquired']
SKIP = {'timestamp', 'scenario', 'run_id', 'example_type', 'action_label'}


def eta2(values, groups):
    d = pd.DataFrame({'v': values, 'g': groups}).dropna()
    if len(d) < 5 or d.v.var() == 0:
        return 0.0
    grand = d.v.mean()
    between = sum(len(x) * (x.mean() - grand) ** 2 for _, x in d.groupby('g').v)
    total = ((d.v - grand) ** 2).sum()
    return between / total if total > 0 else 0.0


# read all good runs; runs may have different columns -> note which run has which
raw = {}
for f in sorted(glob.glob(os.path.join(CLEANED_DIR, '*_good_*.csv'))):
    df = pd.read_csv(f).reset_index(drop=True)
    if 'pos_x' in df:
        df['wheel_speed_from_pos_x'] = df['pos_x'].diff() * 10
    if 'distance_travelled' in df:
        df['speed_from_distance'] = df['distance_travelled'].diff() * 10
    raw['_'.join(os.path.basename(f).split('_')[:3])] = df
all_cols = sorted(set().union(*[set(d.columns) for d in raw.values()]))
has = {c: [r for r, d in raw.items() if c in d.columns] for c in all_cols}

frames, pieces = [], []
for run, df in raw.items():
    df = df.reindex(columns=all_cols)                 # missing column -> empty (NaN)
    frames.append(df)
    seg = (df['action_label'] != df['action_label'].shift()).cumsum()
    groups = [g for _, g in df.groupby(seg)]
    for i, g in enumerate(groups):
        ph = g['action_label'].iloc[0]
        if ph not in PHASES:
            continue
        prev = groups[i - 1] if i > 0 and groups[i - 1]['action_label'].iloc[0] in PHASES else None
        pieces.append((ph, g, prev))

alldf = pd.concat(frames, ignore_index=True)
signals = [c for c in all_cols if c not in SKIP and pd.api.types.is_numeric_dtype(alldf[c])]

rows = []
for s in signals:
    v = alldf[s]
    phase, mean, change, jump = [], [], [], []
    for ph, g, prev in pieces:
        x = g[s].values.astype(float)
        if np.isnan(x).all():
            continue
        phase.append(ph)
        mean.append(np.nanmean(x))
        change.append(np.nanmean(x[-5:]) - np.nanmean(x[:5]))
        jump.append(np.nanmean(x[:5]) - np.nanmean(prev[s].values[-5:].astype(float))
                    if prev is not None and not np.isnan(prev[s].values[-5:].astype(float)).all() else np.nan)
    sc = {'mean': eta2(mean, phase), 'change': eta2(change, phase), 'jump': eta2(jump, phase)}
    best = max(sc, key=sc.get)
    rows.append(dict(signal=s, in_runs=f'{len(has[s])}/{len(raw)}',
                     missing_pct=round(100 * v.isna().mean(), 1),
                     zero_pct=round(100 * (v == 0).mean(), 1),
                     distinct=int(v.nunique()),
                     min=round(float(v.min()), 3) if v.notna().any() else np.nan,
                     max=round(float(v.max()), 3) if v.notna().any() else np.nan,
                     score_mean=round(sc['mean'], 2), score_change=round(sc['change'], 2),
                     score_jump=round(sc['jump'], 2), best=f'{best} ({sc[best]:.2f})'))

t = pd.DataFrame(rows).sort_values('best', key=lambda c: c.str.extract(r'\((.*)\)')[0].astype(float), ascending=False)
pd.set_option('display.width', 230)
print(f'PART 1 + 2: {len(pieces)} phase pieces from {len(raw)} good runs\n')
print(t.to_string(index=False))
print('\nscore: 0 = does not help to tell phases apart, 1 = separates them perfectly')
print('dead signal: zero_pct near 100, or distinct = 1')
missing = {s: [r for r in raw if r not in has[s]] for s in signals if len(has[s]) < len(raw)}
if missing:
    print('\nSignals missing in some runs:')
    for s, rs in missing.items():
        print(f'  {s}: missing in {", ".join(rs)}')

print('\nPART 3: other CSV folders under ~/rnd_ws (first file of each, columns)')
seen = set()
for f in sorted(glob.glob(os.path.expanduser('~/rnd_ws/**/*.csv'), recursive=True)):
    d = os.path.dirname(f)
    if d in seen or os.path.abspath(d) == os.path.abspath(CLEANED_DIR) or 'phase_plots' in d or 'results' in d:
        continue
    seen.add(d)
    try:
        cols = list(pd.read_csv(f, nrows=1).columns)
    except Exception:
        continue
    print(f'\n{d}  ({len(glob.glob(os.path.join(d, "*.csv")))} files)\n  {cols}')
    if len(seen) >= 12:
        break

out = os.path.expanduser('~/rnd_ws/phase_plots/signal_screening.csv')
os.makedirs(os.path.dirname(out), exist_ok=True)
t.to_csv(out, index=False)
print('\nSaved', out)