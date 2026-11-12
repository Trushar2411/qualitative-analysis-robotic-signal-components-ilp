#!/usr/bin/env python3
"""Plot xArm6 joint telemetry with labeled phases; exclude idle samples."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

PHASE_COLORS = {
    'home': '#e7edf3',
    'gripper_opening': '#d8f1e4',
    'pick': '#fff0ca',
    'gripper_closing': '#fbe1e2',
    'lift': '#e2e7ff',
    'place': '#f5e2fa',
    'retract': '#dceef5',
    'return_home': '#e9f1d8',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_file', type=Path)
    parser.add_argument('--output-dir', type=Path, default=None)
    args = parser.parse_args()

    df = pd.read_csv(args.csv_file)
    if 'phase' not in df.columns:
        raise ValueError("CSV must have a 'phase' column")
    time_column = next((c for c in ('bag_time_sec', 'header_stamp_sec') if c in df.columns), None)
    if time_column is None:
        raise ValueError('Missing bag_time_sec or header_stamp_sec time column')

    n_before = len(df)
    df['phase'] = df['phase'].fillna('').astype(str).str.strip()
    df['_orig_index'] = np.arange(len(df))
    df = df.loc[df['phase'].str.lower() != 'idle'].copy()
    if df.empty:
        raise ValueError('No non-idle data available')

    # Original timing is retained, with time zero at the first non-idle sample.
    df['time_s'] = pd.to_numeric(df[time_column], errors='coerce')
    if df['time_s'].isna().any():
        raise ValueError(f'{time_column} contains missing or invalid timestamps')
    df['time_s'] -= df['time_s'].iloc[0]
    # Break plotted lines across any rows removed between non-idle segments.
    df['_segment'] = (df['_orig_index'].diff().fillna(1) != 1).cumsum()

    # Each contiguous phase block gets its own shading and annotation.
    df['_phase_block'] = (
        df['phase'].ne(df['phase'].shift()) |
        df['_segment'].ne(df['_segment'].shift())
    ).cumsum()
    phases = list(df.groupby('_phase_block', sort=False))
    output = args.output_dir or args.csv_file.parent / 'xarm6_plots_with_phases'
    output.mkdir(parents=True, exist_ok=True)
    df.drop(columns=['_orig_index', '_segment', '_phase_block']).to_csv(
        output / 'full_motion_no_idle.csv', index=False
    )

    for kind, units in [('position', 'rad'), ('velocity', 'rad/s'), ('effort', 'N·m')]:
        fig, ax = plt.subplots(figsize=(17, 7.5))
        for _, phase_df in phases:
            phase = phase_df['phase'].iloc[0]
            start, end = phase_df['time_s'].iloc[[0, -1]]
            ax.axvspan(start, end, color=PHASE_COLORS.get(phase, '#eeeeee'), alpha=0.8, zorder=0)
            ax.axvline(start, color='gray', alpha=.35, lw=.8)
            midpoint = (start + end) / 2
            label = phase.replace('_', '\n')
            ax.text(midpoint, 1.02, label, transform=ax.get_xaxis_transform(),
                    ha='center', va='bottom', fontsize=8, rotation=0, clip_on=False)

        plotted = 0
        for joint in range(1, 7):
            column = f'joint{joint}_{kind}'
            if column not in df:
                continue
            signal = pd.to_numeric(df[column], errors='coerce')
            if not signal.notna().any():
                continue
            plotted += 1
            for seg_id, segment in df.groupby('_segment', sort=False):
                ax.plot(segment['time_s'], signal.loc[segment.index], lw=1.3,
                        label=f'Joint {joint}' if seg_id == df['_segment'].iloc[0] else '_nolegend_')

        if not plotted:
            ax.text(.5, .5, f'No valid joint {kind} data in this CSV',
                    transform=ax.transAxes, ha='center', va='center', fontsize=13)

        ax.set_title(f'xArm6 joint {kind} vs. time (idle removed)', fontsize=15, pad=48)
        ax.set_xlabel('Elapsed time since first non-idle sample (s)')
        ax.set_ylabel(f'Joint {kind} ({units})')
        ax.grid(alpha=.22)
        ax.margins(x=0)
        if plotted:
            ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), frameon=False)
        fig.subplots_adjust(top=.80, right=.85)
        for extension in ('png', 'svg'):
            path = output / f'{kind}_vs_time_with_phases.{extension}'
            fig.savefig(path, dpi=250, bbox_inches='tight')
            print('Saved:', path)
        plt.close(fig)

    print(f'Removed idle rows: {n_before - len(df)}; kept: {len(df)}')
    print('Output directory:', output)


if __name__ == '__main__':
    main()
