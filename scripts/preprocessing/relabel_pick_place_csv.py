#!/usr/bin/env python3
"""Regenerate estimated phases from exported gripper widths, preserving signals.

Uses the original first-crossing heuristic and 10-sample pick/place windows.
These are inferred labels, not independently verified task annotations.
"""

import argparse
import csv
import io
import math
from collections import Counter
from pathlib import Path

CLOSED_THRESHOLD = 0.05
OPEN_THRESHOLD = 0.06
PHASE_ORDER = ['approach', 'pick', 'transport', 'place', 'retract']


def create_phase_labels(widths):
    if not widths or not all(math.isfinite(w) for w in widths):
        raise ValueError('Empty or non-finite gripper widths')
    pick = next((i for i in range(1, len(widths))
                 if widths[i] < CLOSED_THRESHOLD <= widths[i - 1]), None)
    if pick is None:
        raise ValueError('No closing threshold crossing')
    place = next((i for i in range(pick + 1, len(widths))
                  if widths[i] > OPEN_THRESHOLD >= widths[i - 1]), None)
    if place is None:
        raise ValueError('No opening threshold crossing after pick')
    pick_end = min(pick + 10, place)
    place_end = min(place + 10, len(widths))
    return (['approach'] * pick + ['pick'] * (pick_end - pick)
            + ['transport'] * (place - pick_end)
            + ['place'] * (place_end - place)
            + ['retract'] * (len(widths) - place_end))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path,
                        default=Path(__file__).resolve().parents[2] / 'pick_place_csv')
    parser.add_argument('--demos', type=int, nargs='+',
                        help='Only relabel these demonstration IDs')
    args = parser.parse_args()
    files = sorted(args.directory.glob('demo_*.csv'),
                   key=lambda p: int(p.stem.split('_')[-1]))
    if args.demos is not None:
        requested = set(args.demos)
        files = [p for p in files if int(p.stem.split('_')[-1]) in requested]
        missing = requested - {int(p.stem.split('_')[-1]) for p in files}
        if missing:
            raise ValueError(f'Requested demonstration IDs not found: {sorted(missing)}')
    if not files:
        raise ValueError('No demonstration CSV files found')
    pending = []
    totals = Counter()
    sequences = Counter()
    # Validate every demonstration before overwriting any file.
    for path in files:
        original = path.read_bytes()
        rows = list(csv.reader(io.StringIO(original.decode('utf-8'))))
        header, data = rows[0], rows[1:]
        phase_col = header.index('phase')
        width_col = header.index('gripper_width')
        if any(len(row) != len(header) for row in data):
            raise ValueError(f'{path.name}: inconsistent columns')
        try:
            labels = create_phase_labels([float(row[width_col]) for row in data])
        except ValueError as exc:
            raise ValueError(f'{path.name}: {exc}') from exc
        runs = [label for i, label in enumerate(labels)
                if i == 0 or label != labels[i - 1]]
        if runs != [phase for phase in PHASE_ORDER if phase in runs]:
            raise ValueError(f'{path.name}: invalid phase sequence: {runs}')
        sequences[','.join(runs)] += 1
        # Change only the final phase field; retain numeric text and line endings.
        if phase_col != len(header) - 1:
            raise ValueError(f'{path.name}: expected phase as final column')
        lines = original.splitlines(keepends=True)
        if len(lines) != len(rows):
            raise ValueError(f'{path.name}: unexpected multiline CSV records')
        output = [lines[0]]
        for line, label in zip(lines[1:], labels):
            body = line.rstrip(b'\r\n')
            ending = line[len(body):]
            output.append(body.rsplit(b',', 1)[0] + b',' + label.encode() + ending)
        pending.append((path, b''.join(output), data, phase_col, labels))
        totals.update(labels)
        if args.demos is not None:
            print(f'{path.name}: {dict(Counter(labels))}')
    for path, output, old_rows, phase_col, labels in pending:
        path.write_bytes(output)
        with path.open(newline='', encoding='utf-8') as handle:
            saved = list(csv.reader(handle))[1:]
        assert len(saved) == len(old_rows), path
        assert all(a[:phase_col] == b[:phase_col]
                   for a, b in zip(old_rows, saved)), path
        assert [row[phase_col] for row in saved] == labels, path
    print(f'Regenerated and verified {len(files)} CSV files; {sum(totals.values())} rows.')
    print(f'Phase counts: {dict(totals)}')
    print('All rows labeled in valid phase order; all signal values preserved.')
    print(f'Phase sequences: {dict(sequences)}')
    ids = {int(p.stem.split('_')[-1]) for p in args.directory.glob('demo_*.csv')}
    print(f'Missing demo IDs within 0..{max(ids)}: {sorted(set(range(max(ids) + 1)) - ids)}')


if __name__ == '__main__':
    main()
