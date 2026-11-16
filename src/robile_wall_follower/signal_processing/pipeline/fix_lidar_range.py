#!/usr/bin/env python3
"""
fix_lidar_range.py  -  clean the lidar columns in data_cleaned/

WHAT IT DOES
  1. Makes a backup:  data_cleaned/  ->  data_cleaned_backup_before_cap/  (only the first time)
  2. If a cleaned file is missing one of the 4 lidars (pw_good_06, pw_good_09 miss lidar_front),
     it copies that column back from the matching raw file (matched by timestamp).
  3. Caps every lidar value above MAX_RANGE to MAX_RANGE.
     65.53 means "nothing in range" -> becomes MAX_RANGE ("far away").

HOW TO RUN
  cd ~/rnd_ws/src/robile_wall_follower/signal_processing
  python3 fix_lidar_range.py
"""
import os, glob, shutil
import pandas as pd

RAW_DIRS    = [os.path.expanduser('~/rnd_ws/data'), os.path.expanduser('~/rnd_ws/data_pillar')]
CLEANED_DIR = os.path.expanduser('~/rnd_ws/data_cleaned')
BACKUP_DIR  = os.path.expanduser('~/rnd_ws/data_cleaned_backup_before_cap')
LIDARS      = ['lidar_left', 'lidar_right', 'lidar_front', 'lidar_front_right']
MAX_RANGE   = 10.0   # metres; everything above is treated as "far / nothing in range"


def to_time(col):
    num = pd.to_numeric(col, errors='coerce')
    if num.notna().mean() > 0.9:
        return pd.to_datetime(num, unit='s', errors='coerce')
    return pd.to_datetime(col, errors='coerce')


def load_raw_files():
    raws = []
    for d in RAW_DIRS:
        for f in sorted(glob.glob(os.path.join(d, '*.csv'))):
            df = pd.read_csv(f)
            if 'timestamp' not in df.columns:
                continue
            df['_t'] = to_time(df['timestamp'])
            raws.append((f, df))
    return raws


def find_raw(clean_df, raws):
    """Raw file whose time range contains the middle timestamp of the cleaned file."""
    t_mid = to_time(clean_df['timestamp']).iloc[len(clean_df) // 2]
    for f, df in raws:
        if df['_t'].min() <= t_mid <= df['_t'].max():
            return f, df
    return None, None


def main():
    # 1. backup
    if not os.path.exists(BACKUP_DIR):
        shutil.copytree(CLEANED_DIR, BACKUP_DIR)
        print(f'Backup made: {BACKUP_DIR}')
    else:
        print(f'Backup already exists (not overwritten): {BACKUP_DIR}')

    raws = load_raw_files()
    files = sorted(glob.glob(os.path.join(CLEANED_DIR, '*.csv')))
    print(f'\nProcessing {len(files)} cleaned files (MAX_RANGE = {MAX_RANGE} m)\n')

    for f in files:
        df = pd.read_csv(f)
        name = os.path.basename(f)
        notes = []

        # 2. put back missing lidar columns from the raw file
        missing = [s for s in LIDARS if s not in df.columns]
        if missing:
            raw_f, raw = find_raw(df, raws)
            if raw is None:
                notes.append(f'MISSING {missing}, raw file not found!')
            else:
                df['_t'] = to_time(df['timestamp'])
                cols = [s for s in missing if s in raw.columns]
                merged = df.merge(raw[['_t'] + cols].drop_duplicates('_t'), on='_t', how='left')
                df = merged.drop(columns='_t')
                n_nan = int(df[cols].isna().sum().sum())
                notes.append(f'added {cols} from {os.path.basename(raw_f)}'
                             + (f' ({n_nan} rows unmatched)' if n_nan else ''))
                # keep a sensible column order: lidars before action_label
                if 'action_label' in df.columns:
                    order = [c for c in df.columns if c != 'action_label'] + ['action_label']
                    df = df[order]

        # 3. cap
        for s in LIDARS:
            if s in df.columns:
                too_far = df[s] > MAX_RANGE
                if too_far.any():
                    notes.append(f'{s}: {too_far.mean()*100:.0f}% capped')
                df.loc[too_far, s] = MAX_RANGE

        df.to_csv(f, index=False)
        print(f'  {name:<38} ' + ('; '.join(notes) if notes else 'nothing to change'))

    print('\nDone. Original files are in', BACKUP_DIR)


if __name__ == '__main__':
    main()