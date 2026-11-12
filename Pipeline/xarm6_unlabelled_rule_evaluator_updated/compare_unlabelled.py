#!/usr/bin/env python3
"""Apply learned Popper RAW/PLA hypotheses to unseen xArm6 telemetry.
No ground truth is inferred. Error/accuracy metrics require --ground-truth.
No Popper installation required. pip install numpy pandas matplotlib
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PHASES = ['pick','gripper_closing','lift','place','gripper_opening','retract','return_home']
ALL_STATES={'increases','decreases','constant'}
CLAUSE_RE=re.compile(r'([a-z][a-z0-9_]*)\s*\(\s*(?:V\d+|A)\s*\)')
PRED_RE=re.compile(r'^(.*)_(increases|decreases|constant)$')

def parse_hypothesis(text):
    out=[]
    for clause in str(text).split('.'):
        if ':-' not in clause: continue
        pred=CLAUSE_RE.findall(clause.split(':-',1)[1])
        if pred: out.append(tuple(pred))
    return out

def load_rules(path,mode='majority'):
    df=pd.read_csv(path)
    if not {'phase','status','canonical_hypothesis'}.issubset(df.columns):
        raise ValueError(f'{path}: missing columns phase/status/canonical_hypothesis')
    chosen={}
    for phase in PHASES:
        rows=df[(df.phase==phase)&(df.status=='ok')]
        if rows.empty: raise ValueError(f'No successful rule for {phase} in {path}')
        counts=Counter(rows.canonical_hypothesis.dropna())
        if not counts: raise ValueError(f'No hypothesis for phase {phase}')
        if mode=='majority':
            chosen[phase]=[(parse_hypothesis(counts.most_common(1)[0][0]),1.)]
        else:
            chosen[phase]=[(parse_hypothesis(text),n/sum(counts.values())) for text,n in counts.items()]
    return chosen

def needed_signals(*rulesets):
    preds=set()
    for rules in rulesets:
        for versions in rules.values():
            for clauses,weight in versions:
                for c in clauses: preds.update(c)
    signals=set()
    for p in preds:
        m=PRED_RE.fullmatch(p)
        if not m: raise ValueError(f'Unknown predicate format: {p}')
        signals.add(m.group(1))
    return sorted(signals)

def normalize_columns(df):
    """Map compatible finger names used by other robot exporters.

    Aliases assume identical physical signals and units; the user must verify this.
    """
    aliases = {
        'left_finger_joint_position': 'left_finger_position',
        'left_finger_joint_velocity': 'left_finger_velocity',
        'left_finger_joint_effort': 'left_finger_effort',
        'right_finger_joint_position': 'right_finger_position',
        'right_finger_joint_velocity': 'right_finger_velocity',
        'right_finger_joint_effort': 'right_finger_effort',
    }
    changes=[]
    for expected, available in aliases.items():
        if expected not in df.columns and available in df.columns:
            df[expected] = df[available]
            changes.append(f'{available} -> {expected}')
    if changes:
        print('Column mappings (verify sensor semantics/units):', '; '.join(changes))
    return df

def get_time(df):
    if 'elapsed_sec' in df: t=pd.to_numeric(df.elapsed_sec,errors='coerce').to_numpy(float)
    elif 'header_stamp_sec' in df: t=pd.to_numeric(df.header_stamp_sec,errors='coerce').to_numpy(float)
    elif 'bag_time_sec' in df: t=pd.to_numeric(df.bag_time_sec,errors='coerce').to_numpy(float)
    else: raise ValueError('Provide elapsed_sec, header_stamp_sec or bag_time_sec for timestamped predictions')
    if not np.isfinite(t).all() or len(t)<3 or np.any(np.diff(t)<=0):
        raise ValueError('Timestamps must be numeric and strictly increasing (sort/drop duplicates first)')
    return t-t[0],float(np.median(np.diff(t)))

def thresholds(signals,config):
    result={}
    for s in signals:
        default=0.001 if s.endswith('_effort') else 0.0001
        result[s]=float(config.get(s,default))
    return result

def raw_predicates(df,signals,eps):
    n=len(df);out={}
    for sig in signals:
        if sig not in df: raise ValueError(f'Missing RAW column: {sig}')
        a=pd.to_numeric(df[sig],errors='coerce').to_numpy(float)
        delta=np.full(n,np.nan);delta[:-1]=np.diff(a)
        out[sig+'_increases']=(delta>eps[sig]);out[sig+'_decreases']=(delta<-eps[sig]);out[sig+'_constant']=(np.abs(delta)<=eps[sig])
    return out

def pla_predicates(df,signals,eps,window,pla_df=None,pla_threshold_factor=1.0):
    n=len(df);out={sig+'_'+state:np.zeros(n,dtype=bool) for sig in signals for state in ALL_STATES}
    if pla_df is not None:
        if len(pla_df)!=n: raise ValueError('--pla-csv must have exactly the same rows as raw CSV')
        if 'header_stamp_sec' in df and 'header_stamp_sec' in pla_df:
            a=pd.to_numeric(df.header_stamp_sec,errors='coerce').to_numpy(float)
            b=pd.to_numeric(pla_df.header_stamp_sec,errors='coerce').to_numpy(float)
            if not np.allclose(a,b,atol=1e-4,rtol=0): raise ValueError('PLA timestamps do not match RAW timestamps')
        for sig in signals:
            col=sig+'_trend'
            if col not in pla_df: raise ValueError(f'Missing PLA trend column: {col}')
            v=pla_df[col].astype(str).str.strip().str.lower().to_numpy()
            for state in ALL_STATES:out[sig+'_'+state]=v==state
        # Convert existing trends to window votes, same as PLA generator with min_fraction=.8.
        for start in range(0,n,window):
            end=min(start+window,n)
            if end-start < int(np.ceil(.8*window)):
                for sig in signals:
                    for state in ALL_STATES:out[sig+'_'+state][start:end]=False
                continue
            for sig in signals:
                counts={st:int(out[sig+'_'+st][start:end].sum()) for st in ALL_STATES}
                ranked=sorted(counts,key=lambda x:counts[x],reverse=True)
                if counts[ranked[0]]<int(np.ceil(.8*(end-start))) or counts[ranked[0]]==counts[ranked[1]]:
                    selected=None
                else:selected=ranked[0]
                for state in ALL_STATES:out[sig+'_'+state][start:end]=state==selected
    else:
        # Deployment-friendly approximation: slope over full unlabelled windows. This is NOT
        # guaranteed to match PLA segmentation/reconstruction that produced training *_trend.
        for start in range(0,n,window):
            end=min(start+window,n)
            if end-start<int(np.ceil(.8*window)):continue
            x=np.arange(end-start,dtype=float)
            x-=x.mean();denom=float(x@x)
            for sig in signals:
                if sig not in df: raise ValueError(f'Missing column for PLA fitting: {sig}')
                v=pd.to_numeric(df[sig].iloc[start:end],errors='coerce').to_numpy(float)
                if not np.isfinite(v).all():continue
                slope=float(x@(v-v.mean())/denom)
                th=eps[sig]*pla_threshold_factor
                state='increases' if slope>th else 'decreases' if slope<-th else 'constant'
                out[sig+'_'+state][start:end]=True
    return out

def evaluate(predicates,rules,n):
    predictions={}
    for phase,variants in rules.items():
        score=np.zeros(n,float)
        for clauses,weight in variants:
            total=np.zeros(n,bool)
            for clause in clauses:
                activated=np.ones(n,bool)
                for pred in clause:
                    if pred not in predicates: raise ValueError(f'Predicate {pred} unavailable')
                    activated &= predicates[pred]
                total |= activated
            score+=weight*total.astype(float)
        predictions[phase]=score
    return predictions

def majority_smooth(arr,samples,min_fraction=.5):
    if samples<=1:return arr.copy()
    return pd.Series(arr.astype(float)).rolling(samples,center=True,min_periods=1).mean().to_numpy()>=min_fraction

def get_episodes(mask,t,dt,min_duration):
    mask=np.asarray(mask,bool)
    starts=np.flatnonzero(mask & ~np.r_[False,mask[:-1]])
    ends=np.flatnonzero(mask & ~np.r_[mask[1:],False])+1
    result=[]
    for a,b in zip(starts,ends):
        start=float(t[a]);end=float(t[b]) if b<len(t) else float(t[-1]+dt)
        if end-start>=min_duration-1e-7:result.append((start,end,int(a),int(b)))
    return result

def iou(a,b):
    overlap=max(0.,min(a[1],b[1])-max(a[0],b[0]))
    return overlap/(max(a[1],b[1])-min(a[0],b[0])) if overlap else 0.

def match(truth,preds,cutoff):
    pairs=sorted(((iou(a,b),i,j) for i,a in enumerate(truth) for j,b in enumerate(preds)),reverse=True)
    taken_t=set();taken_p=set();found=[]
    for score,i,j in pairs:
        if score<cutoff: break
        if i in taken_t or j in taken_p:continue
        taken_t.add(i);taken_p.add(j);found.append((truth[i],preds[j],score))
    return found,len(truth)-len(taken_t),len(preds)-len(taken_p)

def ground_truth(raw,source,t):
    if source is None:return None
    if source=='embedded':
        if 'phase' not in raw:raise ValueError('Input CSV does not include phase ground truth')
        return raw.phase.astype(str).str.strip().str.lower().to_numpy()
    d=pd.read_csv(source)
    if 'phase' in d and len(d)==len(raw):
        if 'header_stamp_sec' in raw and 'header_stamp_sec' in d:
            if not np.allclose(raw.header_stamp_sec,d.header_stamp_sec,rtol=0,atol=1e-4):raise ValueError('Ground truth timestamps mismatch')
        return d.phase.astype(str).str.strip().str.lower().to_numpy()
    if {'phase','start_s','end_s'}.issubset(d.columns):
        y=np.full(len(t),'unlabelled',dtype=object)
        for _,r in d.iterrows():y[(t>=float(r.start_s))&(t<float(r.end_s))]=str(r.phase).strip().lower()
        return y
    raise ValueError('Ground truth requires phase column matching input rows, or phase,start_s,end_s intervals in seconds from recording start')

def numbers(pred,truth):
    tp=int((pred&truth).sum());fp=int((pred&~truth).sum());fn=int((~pred&truth).sum());tn=int((~pred&~truth).sum())
    precision=tp/(tp+fp) if tp+fp else 0.;recall=tp/(tp+fn) if tp+fn else 0.
    f1=2*precision*recall/(precision+recall) if precision+recall else 0.
    den=np.sqrt((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn))
    mcc=(tp*tn-fp*fn)/den if den else 0.
    return {'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision':precision,'recall':recall,'f1':f1,'mcc':mcc,'specificity':tn/(tn+fp) if tn+fp else 0.}

def ordered_sequence(episodes_by_phase):
    # Greedy timeline proposal; output is explicitly heuristic, not ground truth.
    selected=[];last_end=-np.inf
    for phase in PHASES:
        candidates=[e for e in episodes_by_phase[phase] if e[0]>=last_end-1e-6]
        if not candidates: selected.append({'phase':phase,'status':'NOT_DETECTED','start_s':np.nan,'end_s':np.nan,'duration_s':np.nan});continue
        # earliest subsequent episode prevents selection of an unrelated later episode by duration
        e=min(candidates,key=lambda x:x[0]);last_end=e[1]
        selected.append({'phase':phase,'status':'DETECTED','start_s':e[0],'end_s':e[1],'duration_s':e[1]-e[0]})
    return selected

def figure_timeline(out,t,truth,detected):
    fig,axes=plt.subplots(len(PHASES),1,figsize=(15,10),sharex=True)
    for j,phase in enumerate(PHASES):
        ax=axes[j];ax.set_ylabel(phase.replace('_',' '),rotation=0,labelpad=80,va='center')
        if truth is not None:ax.fill_between(t,0,1,where=(truth==phase),step='post',alpha=.22,color='gray',label='Truth' if j==0 else None)
        for method,y,color in [('RAW',detected['RAW'][phase],'tab:blue'),('PLA',detected['PLA'][phase],'tab:orange')]:
            ax.step(t,y.astype(float)*(.7 if method=='RAW' else .35),where='post',label=method if j==0 else None,color=color,lw=1.1)
        ax.set_ylim(-.03,1.02);ax.set_yticks([]);ax.grid(alpha=.15)
    axes[0].legend(loc='upper right',ncol=3)
    axes[-1].set_xlabel('Seconds since start of recording')
    fig.suptitle('Popper rule activations on new recording (RAW vs PLA)')
    fig.tight_layout();fig.savefig(out/'phase_timeline.png',dpi=165);fig.savefig(out/'phase_timeline.pdf');plt.close(fig)

def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument('input_csv',type=Path,help='Unlabelled xArm6 raw telemetry CSV')
    ap.add_argument('--raw-results',type=Path,default=Path(__file__).with_name('all_results_raw.csv'))
    ap.add_argument('--pla-results',type=Path,default=Path(__file__).with_name('all_results_pla.csv'))
    ap.add_argument('--pla-csv',type=Path,help='Optional aligned PLA-reconstructed CSV with *_trend columns; labels ignored')
    ap.add_argument('--ground-truth',help="Optional CSV with phase per row OR phase,start_s,end_s intervals; 'embedded' uses input phase")
    ap.add_argument('--raw-manifest',type=Path,default=Path(__file__).with_name('raw_thresholds.json'))
    ap.add_argument('--pla-window',type=int,default=20)
    ap.add_argument('--pla-slope-factor',type=float,default=1.,help='Threshold multiplier for approximate PLA slopes if --pla-csv absent')
    ap.add_argument('--joint5-threshold',type=float,default=0.00001,help='Override Joint 5 POSITION threshold for both RAW adjacent differences and PLA slope (rad/sample); default uses manifest')
    ap.add_argument('--hypotheses',choices=['majority','ensemble'],default='majority',help='Most frequent rule, or weighted vote of all 10 learned versions')
    ap.add_argument('--ensemble-threshold',type=float,default=.5)
    ap.add_argument('--smoothing-sec',type=float,default=.20)
    ap.add_argument('--min-episode-sec',type=float,default=.20)
    ap.add_argument('--episode-iou-cutoff',type=float,default=.10)
    ap.add_argument('--out',type=Path,default=Path('unlabelled_evaluation'))
    args=ap.parse_args()
    if args.pla_window<2:ap.error('--pla-window must be at least 2')
    if args.smoothing_sec<0 or args.min_episode_sec<0:ap.error('Smoothing/episode seconds must be nonnegative')
    raw=normalize_columns(pd.read_csv(args.input_csv))
    t,dt=get_time(raw);n=len(raw)
    config=json.loads(args.raw_manifest.read_text()) if args.raw_manifest.exists() else {}
    if 'thresholds' in config:config=config['thresholds']
    rules={'RAW':load_rules(args.raw_results,args.hypotheses),'PLA':load_rules(args.pla_results,args.hypotheses)}
    req=needed_signals(rules['RAW'],rules['PLA']);eps=thresholds(req,config)
    if args.joint5_threshold is not None:
        if args.joint5_threshold < 0: ap.error('--joint5-threshold must be nonnegative')
        eps['joint5_position']=args.joint5_threshold
        print(f'Joint 5 position directional threshold: {args.joint5_threshold:g} rad/sample (RAW delta; PLA fitted slope)')
    needed_raw=needed_signals(rules['RAW']);needed_pla=needed_signals(rules['PLA'])
    # Required RAW signals are checked without using labels.
    raw_fs=raw_predicates(raw,needed_raw,eps)
    pla_csv=normalize_columns(pd.read_csv(args.pla_csv)) if args.pla_csv else None
    pla_fs=pla_predicates(raw,needed_pla,eps,args.pla_window,pla_csv,args.pla_slope_factor)
    scores={'RAW':evaluate(raw_fs,rules['RAW'],n),'PLA':evaluate(pla_fs,rules['PLA'],n)}
    truth=ground_truth(raw,args.ground_truth,t)
    args.out.mkdir(parents=True,exist_ok=True)
    labels=pd.DataFrame({'elapsed_sec':t})
    if truth is not None:labels['ground_truth_phase']=truth
    smooth_n=max(1,round(args.smoothing_sec/dt))
    detected={};ep_rows=[];summary=[];accuracy=[];bounds=[];seq=[]
    for method in ['RAW','PLA']:
        detected[method]={};epmap={}
        for phase in PHASES:
            sc=scores[method][phase]
            active=sc>=args.ensemble_threshold
            sm=majority_smooth(active,smooth_n)
            eps_=get_episodes(sm,t,dt,args.min_episode_sec)
            pred=np.zeros(n,bool)
            for start,end,a,b in eps_:pred[a:b]=True
            detected[method][phase]=pred
            labels[f'{method.lower()}_{phase}_score']=sc
            labels[f'{method.lower()}_{phase}_active']=pred.astype(int)
            epmap[phase]=eps_
            for start,end,a,b in eps_:
                ep_rows.append({'method':method,'phase':phase,'start_s':start,'end_s':end,'duration_s':end-start})
            item={'method':method,'phase':phase,'detected_episodes':len(eps_),'active_duration_s':round(float(pred.sum()*dt),3),'active_fraction':float(pred.mean())}
            if truth is not None:
                target=truth==phase
                item.update(numbers(pred,target))
                true_eps=get_episodes(target,t,dt,0)
                matches,missed,extra=match(true_eps,eps_,args.episode_iou_cutoff)
                item.update({'true_episodes':len(true_eps),'matched_episodes':len(matches),'missed_episodes':missed,'extra_episodes':extra,
                             'onset_mae_s':float(np.mean([abs(a[0]-b[0]) for a,b,i in matches])) if matches else np.nan,
                             'offset_mae_s':float(np.mean([abs(a[1]-b[1]) for a,b,i in matches])) if matches else np.nan,
                             'boundary_mae_s':float(np.mean([v for a,b,i in matches for v in (abs(a[0]-b[0]),abs(a[1]-b[1]))])) if matches else np.nan,
                             'mean_episode_iou':float(np.mean([score for a,b,score in matches])) if matches else np.nan})
                accuracy.append(item.copy())
                for actual,predicted,i in matches:
                    bounds.append({'method':method,'phase':phase,'actual_start_s':actual[0],'predicted_start_s':predicted[0],
                                   'actual_end_s':actual[1],'predicted_end_s':predicted[1],
                                   'onset_abs_error_s':abs(actual[0]-predicted[0]),'offset_abs_error_s':abs(actual[1]-predicted[1]),'episode_iou':i})
            summary.append(item)
        for p in ordered_sequence(epmap): seq.append({'method':method,**p})
    labels.to_csv(args.out/'timestamped_predictions.csv',index=False)
    pd.DataFrame(ep_rows,columns=['method','phase','start_s','end_s','duration_s']).to_csv(args.out/'all_detected_episodes.csv',index=False)
    pd.DataFrame(summary).to_csv(args.out/'per_phase_summary.csv',index=False)
    pd.DataFrame(seq).to_csv(args.out/'ordered_sequence_proposals.csv',index=False)
    if truth is not None:
        pd.DataFrame(accuracy).to_csv(args.out/'ground_truth_accuracy.csv',index=False)
        pd.DataFrame(bounds).to_csv(args.out/'matched_boundary_errors.csv',index=False)
        macro=pd.DataFrame(accuracy).groupby('method',as_index=False)[['precision','recall','f1','mcc','specificity']].mean()
        macro.to_csv(args.out/'accuracy_macro.csv',index=False)
        print('\nGROUND-TRUTH MACRO SCORES (time-aligned):\n'+macro.to_string(index=False,float_format=lambda x:f'{x:.4f}'))
        for metric in ('f1','mcc'):
            winner=macro.loc[macro[metric].idxmax(),'method'];print(f'Better by mean {metric}: {winner} (on this recording)')
    else:
        print('\nNO GROUND TRUTH: F1, precision, MCC, onset/offset error and true superiority are NOT COMPUTABLE.')
    print('\nORDERED EPISODE PROPOSALS (heuristic; no accuracy claim):\n'+pd.DataFrame(seq).to_string(index=False,float_format=lambda x:f'{x:.2f}'))
    figure_timeline(args.out,t,truth,detected)
    info={'input':str(args.input_csv),'samples':n,'seconds':float(t[-1]),'median_sample_interval_sec':dt,
          'rule_selection':args.hypotheses,'pla_source':'existing PLA trend columns' if pla_csv is not None else 'approximate fixed-window least-squares slope on RAW',
          'pla_window_samples':args.pla_window,'joint5_position_threshold':eps.get('joint5_position'),'smoothing_seconds':args.smoothing_sec,'min_episode_sec':args.min_episode_sec,
          'ground_truth_supplied':truth is not None,'caution':'Rule coverage is not accuracy without ground truth. PLA slope fallback is not identical to original training PLA pipeline.'}
    (args.out/'run_info.json').write_text(json.dumps(info,indent=2))
    print('\nOutputs written to',args.out.resolve())

if __name__=='__main__':main()
