#!/usr/bin/env python3
"""Create phase-specific Noisy Popper tasks from EXISTING reconstructed PLA trends.

Only *_trend columns are used as background knowledge. The *_pla reconstructed
numeric columns are not re-approximated or used as facts. Each phase_id segment
is windowed independently to avoid crossing phase boundaries.
"""
import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

PHASES = ('home','gripper_opening','pick','gripper_closing','lift','place','retract','return_home')
TARGET = {p: ('retract_phase' if p == 'retract' else p) for p in PHASES}
SIGNALS = ([f'joint{i}_{kind}' for i in range(1,7) for kind in ('position','velocity')]
           + [f'{side}_finger_joint_{kind}' for side in ('left','right') for kind in ('position','velocity')])
STATES = {'increases','decreases','constant'}


def make_windows(df, n, min_fraction):
    segments = (df['phase_id'].ne(df['phase_id'].shift())).cumsum()
    result = []
    for _, seg in df.groupby(segments,sort=False):
        phase = str(seg['phase'].iloc[0]).strip().lower()
        if phase not in PHASES:
            continue
        for st in range(0,len(seg),n):
            block = seg.iloc[st:st+n]
            if len(block)<math.ceil(n*min_fraction):
                continue
            feats=set()
            for sig in SIGNALS:
                col=sig+'_trend'
                if col not in df:
                    continue
                states=block[col].astype('string').str.strip().str.lower()
                valid=states[states.isin(STATES)]
                if len(valid)<math.ceil(len(block)*0.8):
                    continue
                counts=valid.value_counts()
                # Require a unique dominant label to avoid arbitrary ties
                if len(counts)>1 and counts.iloc[0]==counts.iloc[1]:
                    continue
                state=counts.index[0]
                feats.add(f'{sig}_{state}')
            result.append({'phase':phase,'phase_id':str(seg['phase_id'].iloc[0]),
                           'start_row':int(block.index[0]),'end_row':int(block.index[-1]),
                           'start_sec':float(block['elapsed_sec'].iloc[0]) if 'elapsed_sec' in block else None,
                           'end_sec':float(block['elapsed_sec'].iloc[-1]) if 'elapsed_sec' in block else None,
                           'features':feats})
    return result


def rank_features(windows, pids, nids, cap):
    predicates=sorted(set.union(set(),*(windows[i]['features'] for i in pids+nids)))
    ranking=[]
    for f in predicates:
        p=sum(f in windows[i]['features'] for i in pids)/len(pids)
        q=sum(f in windows[i]['features'] for i in nids)/len(nids)
        score=(p-q)*(0.5+0.5*p)
        if p>0 and score>0:
            ranking.append((score,f,p,q))
    ranking.sort(key=lambda x:(-x[0],x[1]))
    return ranking[:cap]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('csv_file',type=Path)
    ap.add_argument('--out',type=Path,default=Path('generated_pla_3states'))
    ap.add_argument('--window-size',type=int,default=20)
    ap.add_argument('--min-fraction',type=float,default=.8)
    ap.add_argument('--max-predicates',type=int,default=12)
    ap.add_argument('--max-neg-ratio',type=float,default=2)
    ap.add_argument('--seed',type=int,default=42)
    args=ap.parse_args()
    if args.window_size<2: ap.error('window-size must be at least 2')
    if not (0 < args.min_fraction <= 1): ap.error('min-fraction must be in (0,1]')
    if args.max_predicates<1: ap.error('max-predicates must be positive')
    df=pd.read_csv(args.csv_file)
    for col in ('phase','phase_id'):
        if col not in df: ap.error(f'Missing {col}')
    found=[c for c in [sig+'_trend' for sig in SIGNALS] if c in df]
    if not found: ap.error('No expected *_trend columns found')
    windows=make_windows(df,args.window_size,args.min_fraction)
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(args.seed)
    pd.DataFrame([{**{k:v for k,v in w.items() if k!='features'}, 'id':f'w{i:04d}',
                   'feature_count':len(w['features'])} for i,w in enumerate(windows)]).to_csv(out/'windows.csv',index=False)
    manifest={'source':str(args.csv_file.resolve()),'method':'reconstructed_pla_trend_three_states',
              'window_size':args.window_size,'min_fraction':args.min_fraction,
              'max_predicates':args.max_predicates,'max_neg_ratio':args.max_neg_ratio,
              'seed':args.seed,'feature_columns':found,'phases':{}}
    for phase in PHASES:
        positive=[i for i,w in enumerate(windows) if w['phase']==phase]
        negative=[i for i,w in enumerate(windows) if w['phase']!=phase]
        if not positive: raise ValueError(f'No windows for {phase}')
        if args.max_neg_ratio>0:
            limit=min(len(negative),int(round(len(positive)*args.max_neg_ratio)))
            if len(negative)>limit:
                negative=sorted(rng.choice(negative,size=limit,replace=False).tolist())
        selected=rank_features(windows,positive,negative,args.max_predicates)
        if not selected: raise ValueError(f'No discriminating features for {phase}')
        features=[r[1] for r in selected]
        directory=out/phase;directory.mkdir(parents=True,exist_ok=True)
        target=TARGET[phase]
        with (directory/'bk.pl').open('w') as fp:
            fp.write('% PLA trend facts; grouped by predicate; no phase label leakage.\n')
            for feature in sorted(features):
                for i in sorted(positive+negative):
                    if feature in windows[i]['features']:
                        fp.write(f'{feature}(w{i:04d}).\n')
                fp.write('\n')
        with (directory/'exs.pl').open('w') as fp:
            for i in positive: fp.write(f'pos({target}(w{i:04d})).\n')
            for i in negative: fp.write(f'neg({target}(w{i:04d})).\n')
        with (directory/'bias.pl').open('w') as fp:
            fp.write(f'head_pred({target},1).\n')
            for feat in features: fp.write(f'body_pred({feat},1).\n')
            fp.write('max_vars(1).\nmax_body(3).\nmax_clauses(2).\n')
        manifest['phases'][phase]={'target':target,'positive':len(positive),'negative':len(negative),
                                  'selected_predicates':[{'name':f,'score':round(float(s),5),
                                    'positive_rate':round(float(p),4),'negative_rate':round(float(q),4)}
                                    for s,f,p,q in selected]}
        print(f'{phase:17s}: {len(positive):3d} positive, {len(negative):3d} negative, {len(features):2d} predicates; target={target}')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'\nSaved Popper tasks: {out}')
    print('Labels come from 1 recorded cycle: training metrics are not independent test performance.')

if __name__=='__main__': main()
