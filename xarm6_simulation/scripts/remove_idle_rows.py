#!/usr/bin/env python3
"""Copy a joint-state CSV to a new file, excluding idle and unlabelled rows."""
import argparse
import csv
from pathlib import Path


def remove_idle(input_path, output_path):
    input_path = Path(input_path).expanduser()
    output_path = Path(output_path).expanduser()
    if input_path.resolve() == output_path.resolve():
        raise ValueError('Choose a new output file; the original CSV is preserved.')
    removed = 0
    kept = 0
    with input_path.open(newline='') as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or 'phase' not in reader.fieldnames:
            raise ValueError('The input CSV must contain a phase column.')
        with output_path.open('x', newline='') as destination:
            writer = csv.DictWriter(destination, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader:
                if str(row.get('phase', '')).strip().lower() in ('', 'idle'):
                    removed += 1
                else:
                    writer.writerow(row)
                    kept += 1
    return kept, removed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_csv', type=Path)
    parser.add_argument('output_csv', type=Path)
    args = parser.parse_args()
    kept, removed = remove_idle(args.input_csv, args.output_csv)
    print(f'Saved {kept} labelled rows to {args.output_csv}; removed {removed} idle/unlabelled rows.')


if __name__ == '__main__':
    main()
