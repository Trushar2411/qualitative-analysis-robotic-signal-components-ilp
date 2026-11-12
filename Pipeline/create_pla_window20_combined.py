#!/usr/bin/env python3
"""Fit 20-sample phase-aligned PLA to xArm6 position/velocity and plot grouped joints.

Usage:
  python3 create_pla_window20_combined.py 'full_motion_joint_states(20261111-191003).csv'
  python3 create_pla_window20_combined.py input.csv --out-dir PLA_window20
"""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

WINDOW_SIZE = 20
STEP_SIZE = 20
THRESHOLDS = {'position': 0.002, 'velocity': 0.01}  # fitted change per window
STYLE = {'increases': ('Ramp Up', '#1a9b37'),
         'decreases': ('Ramp Down', '#db1e2a'),
         'constant': ('Constant', '#1375b7')}
PHASE_COLORS = ['#d8eaf8', '#f1f1f1', '#fff0ce', '#ececec', '#def0e0',
                '#ebdffa', '#f4f4f4', '#f9dede', '#e9e9e9']

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_file', type=Path)
    parser.add_argument('--out-dir', type=Path, default=None)
    args = parser.parse_args()
    src = args.csv_file.expanduser().resolve()
    if not src.is_file():
        parser.error(f'Cannot find CSV: {src}')
    out = (args.out_dir.expanduser().resolve() if args.out_dir else
           Path(__file__).resolve().parent / 'PLA_window20')
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(src).reset_index(drop=True)
    need = ['header_stamp_sec', 'phase', 'phase_id', 'cycle']
    missing = [c for c in need if c not in df.columns]
    if missing:
        parser.error('Missing columns: ' + ', '.join(missing))
    if not df.header_stamp_sec.is_monotonic_increasing:
        parser.error('header_stamp_sec must be time-ordered')

    signals = [c for c in df if c.endswith(('_position', '_velocity'))]
    if not signals:
        parser.error('No position or velocity columns found')
    time = df.header_stamp_sec.to_numpy(float)
    elapsed = time - time[0]
    phase_groups = list(df.groupby('phase_id', sort=False))
    phase_records = []
    for phase_id, group in phase_groups:
        idx = group.index.to_numpy()
        phase_records.append({'phase_id': phase_id, 'phase': str(group.phase.iloc[0]),
                              'start': elapsed[idx[0]], 'end': elapsed[idx[-1]],
                              'start_row': int(idx[0]), 'end_row': int(idx[-1]),
                              'samples': len(idx)})
    phases = pd.DataFrame(phase_records)
    phases.to_csv(out / 'phase_intervals.csv', index=False)

    fitted = df[['header_stamp_sec', 'phase', 'phase_id', 'cycle']].copy()
    fitted.insert(1, 'elapsed_sec', elapsed)
    for col in signals:
        fitted[col + '_pla'] = np.nan
        fitted[col + '_trend'] = ''
    window_rows = []
    for phase_id, group in phase_groups:
        ids = group.index.to_numpy()
        for i, start in enumerate(range(0, len(ids), STEP_SIZE)):
            block = ids[start:start+WINDOW_SIZE]
            if not len(block):
                continue
            x = time[block]
            record = {'phase_id':phase_id,'phase':str(group.phase.iloc[0]),
                      'cycle':int(group.cycle.iloc[0]), 'window_index':i,
                      'start_row':int(block[0]), 'end_row':int(block[-1]),
                      'n_samples':len(block), 'start_elapsed_sec':float(elapsed[block[0]]),
                      'end_elapsed_sec':float(elapsed[block[-1]])}
            for col in signals:
                y = pd.to_numeric(df.iloc[block][col], errors='coerce').to_numpy(float)
                valid = np.isfinite(y) & np.isfinite(x)
                if valid.sum() < 2:
                    slope, delta, trend = np.nan, np.nan, 'missing'
                    yy = np.full(len(block), np.nan)
                else:
                    xc = x[valid].mean()
                    yc = y[valid].mean()
                    dx = x[valid] - xc
                    denom = np.dot(dx, dx)
                    slope = float(np.dot(dx, y[valid]-yc)/denom) if denom > 0 else 0.
                    yy = yc + slope*(x-xc)
                    delta = float(slope*(x[-1]-x[0]))
                    threshold = THRESHOLDS[col.rsplit('_', 1)[-1]]
                    trend = ('increases' if delta > threshold else
                             'decreases' if delta < -threshold else 'constant')
                fitted.loc[block, col+'_pla'] = yy
                fitted.loc[block, col+'_trend'] = trend
                record[col+'_slope_per_sec'] = slope
                record[col+'_change'] = delta
                record[col+'_trend'] = trend
            window_rows.append(record)
    windows = pd.DataFrame(window_rows)
    fitted.to_csv(out / 'pla_window20_reconstructed.csv', index=False)
    windows.to_csv(out / 'pla_window20_features.csv', index=False)

    plt.rcParams.update({'font.size':10, 'axes.grid':True, 'grid.alpha':0.24,
                         'grid.linestyle':'--', 'savefig.facecolor':'white'})
    files = []
    def make_plot(columns, filename, title, unit):
        columns = [c for c in columns if c in df.columns]
        if not columns:
            return
        fig, axes = plt.subplots(len(columns), 1, figsize=(17, 3.0*len(columns)+1.25),
                                 sharex=True, constrained_layout=True)
        axes = np.atleast_1d(axes)
        for ax, col in zip(axes, columns):
            for k, ph in phases.iterrows():
                ax.axvspan(ph.start, ph.end, color=PHASE_COLORS[k % len(PHASE_COLORS)], alpha=.48, lw=0)
                ax.axvline(ph.start, color='#a5a5a5', ls='--', alpha=.36, lw=.8)
            ax.plot(elapsed, df[col].to_numpy(float), color='#777777', lw=.9,
                    alpha=.9, label='Raw signal', zorder=2)
            for row in windows.itertuples(index=False):
                a,b = int(row.start_row),int(row.end_row)
                trend = getattr(row,col+'_trend')
                if trend not in STYLE:
                    continue
                ax.plot(elapsed[a:b+1], fitted.iloc[a:b+1][col+'_pla'],
                        color=STYLE[trend][1], lw=2.0, zorder=3, solid_capstyle='round')
            ax.set_ylabel(f'{col}\n[{unit}]', fontsize=9)
            ax.axhline(0, color='#555',lw=.6,alpha=.45)
            ax.set_xlim(elapsed[0], elapsed[-1])
            ax.margins(y=.13)
            # Annotate phases on every subplot, mirroring the supplied examples.
            top = ax.get_ylim()[1]
            for _, ph in phases.iterrows():
                mid = (ph.start+ph.end)/2
                label = ph.phase.replace('_',' ').title()
                if ph.end-ph.start > 1.5:
                    ax.text(mid, .985, label, transform=ax.get_xaxis_transform(),
                            ha='center', va='top', fontsize=8, color='#333',
                            clip_on=True)
        axes[0].set_title(title+' — 20-sample PLA', fontsize=16, pad=17)
        axes[-1].set_xlabel('Time since run start [s]', fontsize=12)
        handles = [Line2D([0],[0],color='#777',lw=1.2,label='Raw signal')]
        for trend in ('constant','increases','decreases'):
            label,color = STYLE[trend]
            handles.append(Line2D([0],[0],color=color,lw=2.8,label=label))
        fig.legend(handles=handles, loc='lower center', ncol=4,
                   bbox_to_anchor=(.5, -.005), frameon=True, fontsize=10)
        path = out / filename
        fig.savefig(path, dpi=145, bbox_inches='tight')
        plt.close(fig)
        files.append(path)
        print('Saved:', path)

    arm_pos = [f'joint{i}_position' for i in range(1,7)]
    arm_vel = [f'joint{i}_velocity' for i in range(1,7)]
    grip_pos = [c for c in signals if c.endswith('_position') and c not in arm_pos]
    grip_vel = [c for c in signals if c.endswith('_velocity') and c not in arm_vel]
    make_plot(arm_pos, 'all_arm_joint_positions_PLA.png', 'All xArm6 joint positions', 'rad')
    make_plot(arm_vel, 'all_arm_joint_velocities_PLA.png', 'All xArm6 joint velocities', 'rad/s')
    make_plot(grip_pos, 'all_gripper_joint_positions_PLA.png', 'All gripper joint positions', 'rad')
    make_plot(grip_vel, 'all_gripper_joint_velocities_PLA.png', 'All gripper joint velocities', 'rad/s')

    pdf_path = out / 'all_joint_PLA_graphs.pdf'
    with PdfPages(pdf_path) as pdf:
        for image_path in files:
            img=plt.imread(image_path)
            fig=plt.figure(figsize=(13, 16))
            ax=fig.add_axes([0.01, 0.01, 0.98, 0.98]);ax.imshow(img);ax.axis('off')
            pdf.savefig(fig);plt.close(fig)
    zip_path = out.parent / 'PLA_window20_combined_results.zip'
    with ZipFile(zip_path,'w',ZIP_DEFLATED) as z:
        for path in [*files,pdf_path,out/'phase_intervals.csv',
                     out/'pla_window20_features.csv',out/'pla_window20_reconstructed.csv']:
            z.write(path,arcname=path.name)
    print(f'Finished: {len(df)} samples, {len(signals)} position/velocity signals, {len(windows)} windows')
    print('Output:', out)
    print('ZIP:', zip_path)

if __name__=='__main__':
    main()
