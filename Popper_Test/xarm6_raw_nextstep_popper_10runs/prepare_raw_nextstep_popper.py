#!/usr/bin/env python3
"""RAW xArm6 Popper dataset: compare sample i to i+1, without windows/PLA.

Each transition within a phase segment becomes one example. At timestamp i,
features are computed from x[i+1]-x[i]. The last sample of each phase segment
has no transition and is excluded. Negative examples are sampled once (seeded).
"""
import argparse
import json
import re
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd

PHASES = ('home', 'gripper_opening', 'pick', 'gripper_closing', 'lift', 'place', 'retract', 'return_home')
TARGET = {p: ('retract_phase' if p == 'retract' else p) for p in PHASES}
SIGNALS = ([f'joint{i}_{kind}' for i in range(1,7) for kind in ('position','velocity','effort')] +
           [f'{side}_finger_joint_{kind}' for side in ('left','right') for kind in ('position','velocity')])


def get_threshold(signal, args):
    if signal.endswith('_position'):
        return args.position_threshold
    if signal.endswith('_velocity'):
        return args.velocity_threshold
    if signal.endswith('_effort'):
        return args.effort_threshold
    raise ValueError(signal)


def build_transitions(df, args):
    transitions = []
    segment_ids = (df['phase_id'].ne(df['phase_id'].shift()) | df['cycle'].ne(df['cycle'].shift()) |
                   df['phase'].ne(df['phase'].shift())).cumsum()
    for _, block in df.groupby(segment_ids, sort=False):
        phase = str(block['phase'].iloc[0]).strip().lower()
        if phase not in PHASES or len(block) < 2:
            continue
        # Sample differences on adjacent rows ONLY, never across phase boundaries.
        for local_i in range(len(block) - 1):
            a = block.iloc[local_i]
            b = block.iloc[local_i+1]
            feats = set()
            for signal in SIGNALS:
                if signal not in df.columns:
                    continue
                x, y = a[signal], b[signal]
                if not (pd.notna(x) and pd.notna(y)):
                    continue
                delta = float(y) - float(x)
                if not np.isfinite(delta):
                    continue
                eps = get_threshold(signal, args)
                state = 'increases' if delta > eps else 'decreases' if delta < -eps else 'constant'
                feats.add(f'{signal}_{state}')
            if feats:
                transitions.append({'phase': phase, 'phase_id': str(a['phase_id']),
                                    'cycle': str(a['cycle']),
                                    'start_row': int(block.index[local_i]),
                                    'end_row': int(block.index[local_i+1]),
                                    'start_sec': float(a['header_stamp_sec']),
                                    'end_sec': float(b['header_stamp_sec']),
                                    'features': feats})
    return transitions


def rank_predicates(examples, positives, negatives, max_predicates):
    # This is feature screening on the training set; does NOT invent phase-based facts.
    counts_p = Counter(f for i in positives for f in examples[i]['features'])
    counts_n = Counter(f for i in negatives for f in examples[i]['features'])
    ranked = []
    for feature in counts_p:
        pos_rate = counts_p[feature] / len(positives)
        neg_rate = counts_n[feature] / len(negatives)
        score = (pos_rate - neg_rate) * (0.5 + 0.5*pos_rate)
        if score > 0:
            ranked.append((score, feature, pos_rate, neg_rate))
    ranked.sort(key=lambda r: (-r[0], r[1]))
    return ranked[:max_predicates]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_file', type=Path)
    parser.add_argument('--out', type=Path, default=Path('generated_raw_nextstep'))
    parser.add_argument('--position-threshold', type=float, default=0.0001,
                        help='Abs delta rad per adjacent step for joint/finger positions (default 1e-4)')
    parser.add_argument('--velocity-threshold', type=float, default=0.0001,
                        help='Abs delta (rad/s) per adjacent step for velocity (default 1e-4)')
    parser.add_argument('--effort-threshold', type=float, default=0.001,
                        help='Abs delta in effort units per adjacent step (default 1e-3)')
    parser.add_argument('--max-predicates', type=int, default=12)
    parser.add_argument('--max-neg-ratio', type=float, default=2.0,
                        help='Number of negative transitions per positive (default 2); use 0 for all negatives')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    for param in ('position_threshold', 'velocity_threshold', 'effort_threshold'):
        if getattr(args, param) < 0: parser.error(param + ' must be nonnegative')
    if args.max_predicates < 1: parser.error('--max-predicates must be positive')
    if args.max_neg_ratio < 0: parser.error('--max-neg-ratio must be nonnegative')
    df = pd.read_csv(args.csv_file)
    for col in ('phase','phase_id','cycle','header_stamp_sec'):
        if col not in df.columns: parser.error(f'Missing required CSV column: {col}')
    df = df.reset_index(drop=True)
    transitions = build_transitions(df, args)
    if not transitions: parser.error('No valid adjacent-step transitions generated')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    pd.DataFrame([{'id': f't{i:05d}', 'phase': e['phase'], 'phase_id': e['phase_id'],
                   'cycle': e['cycle'], 'start_row': e['start_row'], 'end_row': e['end_row'],
                   'start_sec': e['start_sec'], 'end_sec': e['end_sec'],
                   'n_features': len(e['features'])} for i,e in enumerate(transitions)]).to_csv(out/'transitions.csv',index=False)
    manifest = {'source': str(args.csv_file.resolve()), 'method': 'raw_adjacent_sample_delta_no_window_no_pla',
                'window_size': None, 'feature_operation': 'x[i+1]-x[i]',
                'thresholds': {s: get_threshold(s,args) for s in SIGNALS},
                'max_predicates': args.max_predicates, 'max_neg_ratio': args.max_neg_ratio,
                'seed': args.seed, 'source_rows': len(df), 'transitions': len(transitions), 'phases': {}}
    for phase in PHASES:
        positives = [i for i,ex in enumerate(transitions) if ex['phase']==phase]
        negatives = [i for i,ex in enumerate(transitions) if ex['phase']!=phase]
        if not positives: raise ValueError(f'No positive examples for phase {phase}')
        if args.max_neg_ratio:
            keep = min(len(negatives), int(round(len(positives)*args.max_neg_ratio)))
            if keep < len(negatives):
                negatives = sorted(int(i) for i in rng.choice(negatives,size=keep,replace=False))
        selected = rank_predicates(transitions,positives,negatives,args.max_predicates)
        if not selected:
            raise RuntimeError(f'No discriminative predicates for {phase}; adjust thresholds')
        selected_features = [f for _,f,_,_ in selected]
        taskdir=out/phase
        taskdir.mkdir(parents=True,exist_ok=True)
        target=TARGET[phase]
        # Group all facts by predicate to prevent SWI-Prolog discontiguous warnings.
        with (taskdir/'bk.pl').open('w') as f:
            f.write('% RAW adjacent-step delta facts, no windowing/PLA.\n')
            for feat in sorted(selected_features):
                for i in sorted(positives + negatives):
                    if feat in transitions[i]['features']:
                        f.write(f'{feat}(t{i:05d}).\n')
                f.write('\n')
        with (taskdir/'exs.pl').open('w') as f:
            for i in positives: f.write(f'pos({target}(t{i:05d})).\n')
            for i in negatives: f.write(f'neg({target}(t{i:05d})).\n')
        with (taskdir/'bias.pl').open('w') as f:
            f.write(f'head_pred({target},1).\n')
            for feat in selected_features: f.write(f'body_pred({feat},1).\n')
            f.write('max_vars(1).\nmax_body(3).\nmax_clauses(2).\n')
        manifest['phases'][phase]={'target':target,'positive':len(positives),'negative':len(negatives),
                                   'selected_predicates': [{'name':f,'score':round(float(score),5),
                                      'positive_rate':round(float(p),4), 'negative_rate':round(float(n),4)}
                                                           for score,f,p,n in selected]}
        print(f'{phase:17s}: {len(positives):4d} positive, {len(negatives):4d} negative; '
              f'{len(selected_features):2d} features (target {target})')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('\nSaved Popper tasks to',out)
    print('NOTICE: one cycle only; training scores are not generalisation estimates.')

if __name__=='__main__': main()
