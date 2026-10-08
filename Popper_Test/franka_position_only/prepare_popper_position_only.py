#!/usr/bin/env python3
"""Build five one-vs-rest Popper tasks from per-signal PLA trend rows."""
import argparse
from pathlib import Path
import pandas as pd

PHASES=('approach','pick','transport','place','retract')
SHAPES=('constant','ramp_up','ramp_down')

def prepare(csv_path, dest):
    df=pd.read_csv(csv_path)
    needed={'demonstration','phase','start_index','end_index','signal','position_label'}
    absent=needed-set(df.columns)
    if absent: raise ValueError(f'Missing columns: {sorted(absent)}')
    df['phase']=df['phase'].astype(str).str.strip().str.lower()
    if not set(df.phase).issubset(PHASES): raise ValueError(f'Unknown phase labels: {set(df.phase)-set(PHASES)}')
    if not set(df.position_label).issubset(SHAPES):
        raise ValueError('Expected PLA labels constant/ramp_up/ramp_down')
    key=['demonstration','start_index','end_index']
    counts=df.groupby(key,sort=True)['signal'].agg(['size','nunique'])
    if (counts['size']!=counts['nunique']).any(): raise ValueError('Duplicate signal rows in a window')
    if df.groupby(key).phase.nunique().gt(1).any(): raise ValueError('Conflicting phase labels for window')
    windows=df.groupby(key,sort=True).first().reset_index()[key+['phase']]
    windows['window_id']=['w'+str(i).zfill(4) for i in range(len(windows))]
    df=df.merge(windows,on=key,suffixes=('','_window'),validate='many_to_one')
    out=Path(dest);out.mkdir(parents=True,exist_ok=True)
    windows.to_csv(out/'window_index.csv',index=False)
    # Grounded per-joint trend atoms make each induced clause concise and interpretable.
    signal_names=sorted(df.signal.unique(),key=lambda s:(s.startswith('finger'),s))
    predicate_names=[f'{kind}_{s}_{shape}' for kind in ['position'] for s in signal_names for shape in SHAPES]
    bk_lines=['% Franka PLA position-only facts, grouped by predicate.']
    facts = {pred: [] for pred in predicate_names}
    for row in df.itertuples(index=False):
        pred = f'position_{row.signal}_{row.position_label}'
        facts[pred].append(f'{pred}({row.window_id}).')
    for pred in sorted(facts):
        if facts[pred]:
            bk_lines.extend([f'% {pred}/1', *facts[pred]])
    # Each task has its own BK since Popper expects bk.pl in the task folder.
    for phase in PHASES:
        p=out/phase;p.mkdir(exist_ok=True)
        (p/'bk.pl').write_text('\n'.join(bk_lines)+'\n')
        exs=['% One-vs-rest examples, labels apply to complete windows.']
        exs += [f"{'pos' if r.phase==phase else 'neg'}({phase}({r.window_id}))." for r in windows.itertuples(index=False)]
        (p/'exs.pl').write_text('\n'.join(exs)+'\n')
        # Candidate literals are shape facts only, never phase, ID, or timing fields.
        bias=[f'head_pred({phase},1).']
        bias.extend(f'body_pred({name},1).' for name in predicate_names)
        bias.extend(['max_vars(1).','max_body(3).','max_clauses(3).'])
        (p/'bias.pl').write_text('\n'.join(bias)+'\n')
    print('Demonstrations:',windows.demonstration.nunique())
    print('Windows per phase:\n'+windows.phase.value_counts().reindex(PHASES,fill_value=0).to_string())
    print('Features:',len(predicate_names),'(position trends only on',len(signal_names),'signals)')
    if windows.demonstration.nunique()<2: print('WARNING: Only one demonstration. No independent demonstration-level test is possible.')
    if min(windows.phase.value_counts())<3: print('WARNING: Some phases have fewer than 3 positive windows; expect unstable rules.')
    return windows

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('csv');a.add_argument('--out',default='tasks');args=a.parse_args()
    prepare(args.csv,args.out)
