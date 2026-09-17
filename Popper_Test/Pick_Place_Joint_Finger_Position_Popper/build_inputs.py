#!/usr/bin/env python3
"""Generate independent position-only Popper tasks; never execute Popper."""
import argparse
import csv
import math
from collections import Counter
from pathlib import Path

PHASES = ('approach', 'pick', 'transport', 'place', 'retract')
DIRECTIONS = ('increases', 'decreases', 'constant')
SIGNALS = [(f'joint{j}_position', f'j{j}_pos', 'joint') for j in range(1, 8)] + [
    (f'finger{j}_position', f'finger{j}_pos', 'finger') for j in range(1, 3)]
PREDICATES = [f'{prefix}_{direction}' for _, prefix, _ in SIGNALS
              for direction in DIRECTIONS]


def trend(delta, tolerance):
    return 'increases' if delta > tolerance else (
        'decreases' if delta < -tolerance else 'constant')


def bias(phase):
    head = f'phase_{phase}'
    lines = ['% Position trends only: seven arm joints and two fingers.',
             'max_vars(1).', 'max_body(4).', 'max_clauses(3).', '',
             f'head_pred({head},1).']
    lines += [f'body_pred({p},1).' for p in PREDICATES]
    lines += ['', f'type({head},(state,)).']
    lines += [f'type({p},(state,)).' for p in PREDICATES]
    lines += ['', f'direction({head},(in,)).']
    lines += [f'direction({p},(in,)).' for p in PREDICATES]
    return '\n'.join(lines) + '\n'


def read_states(source, tolerances):
    with source.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        required = {'phase', 'timestep', *(column for column, _, _ in SIGNALS)}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f'{source}: missing columns {sorted(missing)}')
        rows = list(reader)
    if len(rows) < 2:
        raise ValueError(f'{source}: fewer than two samples')
    values = []
    for i, row in enumerate(rows):
        if row['phase'] not in PHASES:
            raise ValueError(f'{source}: unexpected phase at row {i}')
        numbers = [float(row[column]) for column, _, _ in SIGNALS]
        if not all(math.isfinite(value) for value in numbers):
            raise ValueError(f'{source}: non-finite position at row {i}')
        if i and int(row['timestep']) != int(rows[i - 1]['timestep']) + 1:
            raise ValueError(f'{source}: nonconsecutive timesteps at row {i}')
        values.append(numbers)
    states = []
    for i in range(len(rows) - 1):
        if rows[i]['phase'] != rows[i + 1]['phase']:
            continue
        predicates = [f'{prefix}_{trend(values[i + 1][j] - values[i][j], tolerances[kind])}'
                      for j, (_, prefix, kind) in enumerate(SIGNALS)]
        states.append((i, rows[i]['phase'], predicates))
    if not states:
        raise ValueError(f'{source}: no within-phase transitions')
    return rows, states


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    package = Path(__file__).resolve().parent
    parser.add_argument('csv_directory', type=Path, nargs='?',
                        default=package.parents[1] / 'pick_place_csv')
    parser.add_argument('--output', type=Path, default=package / 'datasets')
    parser.add_argument('--joint-deadband', type=float, default=1e-6)
    parser.add_argument('--finger-deadband', type=float, default=1e-6)
    args = parser.parse_args()
    tolerances = {'joint': args.joint_deadband, 'finger': args.finger_deadband}
    if any(not math.isfinite(v) or v < 0 for v in tolerances.values()):
        parser.error('Deadbands must be finite and nonnegative')
    sources = sorted(args.csv_directory.glob('demo_*.csv'),
                     key=lambda p: int(p.stem.split('_')[-1]))
    if not sources:
        parser.error('No demo_*.csv files found')
    # Validate all inputs before creating tasks.
    prepared = [(source, *read_states(source, tolerances)) for source in sources]
    report = []
    total_states = total_facts = 0
    for source, rows, states in prepared:
        counts = Counter(label for _, label, _ in states)
        bk = [f'% Source: pick_place_csv/{source.name}',
              '% sN means data row N -> N+1 (zero-based); phase-boundary pairs omitted.',
              f'% Deadbands: joint={args.joint_deadband}, finger={args.finger_deadband}.']
        # Dynamic declarations make predicates with no facts safely fail in Prolog.
        bk += [f':- dynamic {p}/1.' for p in PREDICATES]
        bk += [f':- discontiguous {p}/1.' for p in PREDICATES]
        bk += [f'{p}(s{i}).' for i, _, predicates in states for p in predicates]
        bk_text = '\n'.join(bk) + '\n'
        for phase in PHASES:
            folder = args.output / source.stem / phase
            folder.mkdir(parents=True, exist_ok=True)
            examples = [f'% Positive: {phase}; negative: other phases in {source.stem}.']
            if counts[phase] == 0:
                examples.append('% NO POSITIVE EXAMPLES: do not interpret this as a learnable phase task.')
            examples += [f"{'pos' if label == phase else 'neg'}(phase_{phase}(s{i}))."
                         for i, label, _ in states]
            files = {'bias.pl': bias(phase), 'bk.pl': bk_text,
                     'exs.pl': '\n'.join(examples) + '\n'}
            for name, content in files.items():
                (folder / name).write_text(content, encoding='utf-8', newline='\n')
                if (folder / name).read_text(encoding='utf-8') != content:
                    raise RuntimeError(f'File verification failed: {folder / name}')
            report.append({'dataset': source.stem, 'source': source.name, 'phase': phase,
                           'rows': len(rows), 'states': len(states),
                           'dropped_boundary_pairs': len(rows) - 1 - len(states),
                           'positives': counts[phase], 'negatives': len(states) - counts[phase],
                           'status': 'ready' if counts[phase] else 'no_positive_examples'})
        total_states += len(states)
        total_facts += 9 * len(states)
    with (args.output / 'input_counts.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(report[0]))
        writer.writeheader()
        writer.writerows(report)
    print(f'{len(sources)} demonstrations; {len(report)} tasks; {len(report) * 3} Prolog files.')
    print(f'{total_states} unique within-run states; {total_facts} position facts before per-phase duplication.')
    print(f'{sum(r["status"] == "no_positive_examples" for r in report)} tasks have no positive examples; see input_counts.csv.')
    print('Generated files verified. Popper was not run.')


if __name__ == '__main__':
    main()
