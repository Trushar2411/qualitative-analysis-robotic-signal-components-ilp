#!/usr/bin/env python3
"""Generate position-only qualitative Popper tasks from xArm6 joint-states CSV."""
import argparse
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

ARM = [f'joint{i}_position' for i in range(1, 7)]
FINGERS = ['left_finger_joint_position', 'right_finger_joint_position']
SIGNALS = ARM + FINGERS
LABELS = ('constant', 'increases', 'decreases')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('csv', nargs='?', default='full_motion_joint_states(20261028-205807).csv')
    p.add_argument('--out', default='tasks')
    p.add_argument('--window', type=int, default=20)
    p.add_argument('--step', type=int, default=20)
    p.add_argument('--threshold', type=float, default=0.004, help='Minimum fitted change (radians) to mark arm movement')
    p.add_argument('--finger-threshold', type=float, default=0.001, help='Minimum fitted finger change (radians)')
    p.add_argument('--min-samples', type=int, default=8)
    a = p.parse_args()
    if a.window < 2 or a.step < 1 or a.min_samples < 2:
        p.error('window>=2, step>=1, min-samples>=2 required')
    src = Path(a.csv)
    if not src.is_file():
        p.error(f'CSV not found: {src}')
    df = pd.read_csv(src)
    must = ['phase', 'phase_id', 'header_stamp_sec'] + SIGNALS
    missing = [x for x in must if x not in df.columns]
    if missing:
        p.error(f'Missing required columns: {missing}')
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    phases = list(dict.fromkeys(df['phase'].astype(str)))
    facts = defaultdict(list)
    indexes = []
    counts = defaultdict(int)
    wid = 0
    # Segment by consecutive phase_id, not merely phase name. This keeps the
    # two gripper_opening steps separate and prevents windows crossing phases.
    groups = (df['phase_id'].astype(str) != df['phase_id'].astype(str).shift()).cumsum()
    for _, part in df.groupby(groups, sort=False):
        phase, phase_id = str(part['phase'].iloc[0]), str(part['phase_id'].iloc[0])
        times = part['header_stamp_sec'].to_numpy(float)
        values = {signal: part[signal].to_numpy(float) for signal in SIGNALS}
        for start in range(0, len(part), a.step):
            end = min(start + a.window, len(part))
            if end-start < a.min_samples:
                continue
            win = f'w{wid:05d}'
            wid += 1
            counts[phase] += 1
            indexes.append({'window_id': win, 'phase': phase, 'phase_id': phase_id,
                            'start_row': int(part.index[start]), 'end_row': int(part.index[end-1]),
                            'start_time_sec': float(times[start]), 'end_time_sec': float(times[end-1]),
                            'samples': end-start})
            for signal in SIGNALS:
                y = values[signal][start:end]
                t = times[start:end]
                good = np.isfinite(y) & np.isfinite(t)
                if good.sum() < a.min_samples:
                    continue
                t, y = t[good], y[good]
                dt = t[-1]-t[0]
                if dt <= 0:
                    continue
                slope = np.polyfit(t-t[0], y, 1)[0]
                change = float(slope * dt)
                threshold = a.finger_threshold if signal in FINGERS else a.threshold
                label = 'increases' if change > threshold else ('decreases' if change < -threshold else 'constant')
                pred = f'{signal.removesuffix("_position")}_position_{label}'
                facts[pred].append(f'{pred}({win}).')
    if not indexes:
        p.error('No complete windows; lower --min-samples or --window')
    pd.DataFrame(indexes).to_csv(out/'window_index.csv', index=False)
    predicates = [f'{signal.removesuffix("_position")}_position_{label}' for signal in SIGNALS for label in LABELS]
    # Grouping facts by predicate prevents discontiguous warnings.
    bk_lines = ['% Position trends from linear approximation within each time window.']
    for pred in sorted(facts):
        bk_lines.extend(['', f'% {pred}', *sorted(set(facts[pred]))])
    bk = '\n'.join(bk_lines) + '\n'
    for phase in phases:
        task = out/phase
        task.mkdir(parents=True, exist_ok=True)
        (task/'bk.pl').write_text(bk)
        examples = ['% One-vs-rest examples for phase: ' + phase]
        for x in indexes:
            tag = 'pos' if x['phase'] == phase else 'neg'
            examples.append(f"{tag}({phase}({x['window_id']})).")
        (task/'exs.pl').write_text('\n'.join(examples) + '\n')
        bias = [f'head_pred({phase},1).'] + [f'body_pred({pr},1).' for pr in predicates]
        bias += ['max_vars(1).', 'max_body(3).', 'max_clauses(3).']
        (task/'bias.pl').write_text('\n'.join(bias)+'\n')
    print(f'Source: {src} | samples: {len(df)} | windows: {len(indexes)}')
    print('Positions only:', ', '.join(SIGNALS))
    print(f'Predicates: {len(predicates)} | window={a.window}, step={a.step}')
    for phase in phases:
        print(f'  {phase:<20}: {counts[phase]} positives / {len(indexes)-counts[phase]} negatives')
    if df.get('cycle', pd.Series([1])).nunique() < 2:
        print('NOTE: Only one recorded cycle. This is training-set learning, not cross-cycle validation.')

if __name__ == '__main__':
    main()
