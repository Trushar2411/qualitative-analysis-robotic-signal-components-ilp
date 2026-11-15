#!/usr/bin/env python3
"""Robust phase-wise PLA for xArm6 CSV. Fits against sample indices to avoid duplicate timestamp failures."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ARM=[f'joint{i}' for i in range(1,7)]
FINGERS=['drive_joint','left_finger_joint','left_inner_knuckle_joint','right_outer_knuckle_joint','right_finger_joint','right_inner_knuckle_joint']
THRESHOLDS={'position':.005,'velocity':.01,'effort':.05,'finger_position':.005}
LABELS=['ramp_up','ramp_down','constant']

def fit_windows(part, cols, window, step, threshold, phase_id):
    rows=[]; n=len(part)
    if n<window:
        return rows
    starts=list(range(0,n-window+1,step))
    if starts[-1]!=n-window: starts.append(n-window)
    for start in starts:
        stop=start+window
        rec={'phase':str(part['phase'].iloc[0]),'phase_occurrence':phase_id,
             'start_row':int(part.index[start]),'end_row':int(part.index[stop-1]),
             'start_time_sec':float(part['bag_time_sec'].iloc[start]),
             'end_time_sec':float(part['bag_time_sec'].iloc[stop-1])}
        for col in cols:
            y=pd.to_numeric(part[col].iloc[start:stop],errors='coerce').to_numpy(float)
            x=np.arange(window,dtype=float)
            valid=np.isfinite(y)
            if valid.sum()<2:
                slope=change=rmse=np.nan; label='unavailable'; intercept=np.nan
            else:
                # Centered sample-index regression is well-conditioned even if timestamps repeat.
                xv=x[valid]; yv=y[valid]
                xc=xv-xv.mean(); denom=np.dot(xc,xc)
                slope=float(np.dot(xc,yv-yv.mean())/denom) if denom>0 else 0.
                intercept=float(yv.mean()-slope*xv.mean())
                predicted=intercept+slope*xv
                change=slope*(xv[-1]-xv[0])
                rmse=float(np.sqrt(np.mean((predicted-yv)**2)))
                label='ramp_up' if change>threshold else 'ramp_down' if change < -threshold else 'constant'
            rec[col+'_slope_per_sample']=slope
            rec[col+'_fitted_change']=change
            rec[col+'_intercept_local']=intercept
            rec[col+'_rmse']=rmse
            rec[col+'_label']=label
        rows.append(rec)
    return rows

def phase_label(part,col,threshold):
    """Overall phase movement from robust endpoint medians, not majority of flat windows."""
    y=pd.to_numeric(part[col],errors='coerce').dropna().to_numpy(float)
    if len(y)<2: return 'unavailable',np.nan
    edge=max(2,min(20,len(y)//10))
    delta=float(np.median(y[-edge:])-np.median(y[:edge]))
    return ('ramp_up' if delta>threshold else 'ramp_down' if delta < -threshold else 'constant'),delta

def make_plot(df,cols,windows,group,path):
    fig,ax=plt.subplots(figsize=(16,7))
    # Use sample index for x-axis: avoids compressed/repeated time coordinates.
    x=np.arange(len(df))
    for col in cols:
        y=pd.to_numeric(df[col],errors='coerce').to_numpy(float)
        line,=ax.plot(x,y,alpha=.38,lw=.85,label=col)
        color=line.get_color()
        if not windows.empty:
            for row in windows.itertuples(index=False):
                a=int(row.start_row); b=int(row.end_row)
                slope=getattr(row,col+'_slope_per_sample')
                intercept=getattr(row,col+'_intercept_local')
                if np.isfinite(slope) and np.isfinite(intercept):
                    ax.plot([a,b],[intercept,intercept+slope*(b-a)],ls='--',lw=1,alpha=.55,color=color)
    phases=df['phase'].astype(str)
    for idx in np.flatnonzero(phases.ne(phases.shift()).to_numpy()):
        ax.axvline(idx,ls=':',lw=.9,alpha=.6)
        ax.annotate(phases.iloc[idx],(idx,1),xycoords=('data','axes fraction'),xytext=(2,-4),textcoords='offset points',rotation=90,va='top',fontsize=8)
    ax.set(title=f'{group}: raw (solid) and PLA fits (dashed)',xlabel='Sample index (idle removed)',ylabel='Signal value')
    ax.grid(alpha=.2);ax.legend(fontsize=8,ncol=2,loc='upper right');fig.tight_layout();fig.savefig(path,dpi=160);plt.close(fig)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv_file');p.add_argument('--output-dir',default='pla_fixed_output')
    p.add_argument('--window',type=int,default=10);p.add_argument('--step',type=int,default=5)
    p.add_argument('--finger-threshold',type=float,default=.005)
    args=p.parse_args()
    if args.window<2 or args.step<1:p.error('window >= 2 and step >= 1 required')
    df=pd.read_csv(args.csv_file)
    if not {'phase','bag_time_sec'}.issubset(df):p.error('Required columns: phase, bag_time_sec')
    df=df.loc[df.phase.notna() & df.phase.astype(str).str.strip().str.lower().ne('idle')].copy().reset_index(drop=True)
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    df.to_csv(out/'without_idle.csv',index=False)
    group_cols={
        'position':[f'{j}_position' for j in ARM],
        'velocity':[f'{j}_velocity' for j in ARM],
        'effort':[f'{j}_effort' for j in ARM],
        'finger_position':[f'{j}_position' for j in FINGERS]
    }
    segments=df.phase.astype(str).ne(df.phase.astype(str).shift()).cumsum()
    occurrence={};parts=[]
    for _,part in df.groupby(segments,sort=False):
        phase=str(part.phase.iloc[0]);occurrence[phase]=occurrence.get(phase,0)+1
        parts.append((phase,occurrence[phase],part))
    for group,cols in group_cols.items():
        missing=[c for c in cols if c not in df]
        if missing:
            print('Skipping',group,'missing',missing);continue
        threshold=args.finger_threshold if group=='finger_position' else THRESHOLDS[group]
        allrows=[];summaries=[]
        for phase,occ,part in parts:
            win=fit_windows(part,cols,args.window,args.step,threshold,occ)
            allrows.extend(win)
            row={'phase':phase,'occurrence':occ,'samples':len(part),'window_count':len(win)}
            for col in cols:
                label,delta=phase_label(part,col,threshold)
                row[col]=label;row[col+'_net_change']=delta
                labels=[w[col+'_label'] for w in win]
                counts={l:labels.count(l) for l in LABELS}
                for l in LABELS:row[col+'_'+l+'_windows']=counts[l]
                row[col+'_majority_window_label']=max(LABELS,key=lambda l:counts[l]) if labels else 'unavailable'
            summaries.append(row)
        wdf=pd.DataFrame(allrows);sdf=pd.DataFrame(summaries)
        sdf.to_csv(out/f'pla_{group}_phase_summary.csv',index=False)
        wdf.to_csv(out/f'pla_{group}_windows.csv',index=False)
        make_plot(df,cols,wdf,group,out/f'pla_{group}.png')
        print('\n'+group.upper());print(sdf[['phase','occurrence']+cols].to_string(index=False))
        if all(df[c].isna().all() for c in cols):print('NOTE: no measured values for this group; labels unavailable.')
    print('\nSaved all results to',out.resolve())

if __name__=='__main__':main()
