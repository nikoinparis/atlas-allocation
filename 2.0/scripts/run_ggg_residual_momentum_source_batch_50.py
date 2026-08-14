#!/usr/bin/env python3
"""Independently reconstruct and test residual momentum with causal GGG."""

from __future__ import annotations

import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv, run_from_artifacts
from systematic_trader.residual_momentum_source import residual_momentum_signal, top_five_weights, volatility_manage
from systematic_trader.trend_reversal_source import blend_with_ggg

ROOT=Path(__file__).resolve().parents[1]; SOURCE=ROOT/'data/frozen_ggg_inputs_v1'; MANIFEST=SOURCE/'manifest.json'
PROGRAM=ROOT/'config/ggg_residual_momentum_source_v1.json'; MODULE=ROOT/'src/systematic_trader/residual_momentum_source.py'; OUTPUT=ROOT/'evidence/ggg_residual_momentum_source_batch_50'
SAVED_SIGNAL=ROOT/'data/audit_comparators/signal_residual_momentum.csv'
SAVED_SIGNAL_SHA256='e9f00a04ecb2e433d861bb3ddfe0ad0a01b0e5c0393872fc010627df560a36fe'

def sha256(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def frame_hash(f): return hashlib.sha256(f.to_csv(float_format='%.17g').encode()).hexdigest()
def frame_difference(a,b):
    i=a.index.intersection(b.index); c=a.columns.intersection(b.columns); v=(a.loc[i,c]-b.loc[i,c]).abs().to_numpy(); return float(np.nanmax(v)) if v.size else float('inf')
def verify_manifest():
    m=json.loads(MANIFEST.read_text()); return all(sha256(SOURCE/r)==h for r,h in m['files'].items())
def metrics(s):
    r=pd.to_numeric(s,errors='coerce').dropna(); w=(1+r).cumprod(); y=len(r)/52; ar=float(r.mean()*52); vol=float(r.std(ddof=1)*np.sqrt(52)); dd=w/w.cummax()-1
    return {'weeks':len(r),'start':str(r.index.min().date()),'end':str(r.index.max().date()),'cagr':float(w.iloc[-1]**(1/y)-1),'arithmetic_ann_return':ar,'ann_vol':vol,'sharpe_zero_rf':ar/vol if vol else np.nan,'max_drawdown':float(dd.min())}
def corr(a,b): return float(pd.concat([a.rename('a'),b.rename('b')],axis=1).dropna().corr().iloc[0,1])
def saved_signal_panel(index,columns):
    df=pd.read_csv(SAVED_SIGNAL,usecols=['Date','Ticker','residual_mom_score_tradable']); df['Date']=pd.to_datetime(df['Date']).dt.tz_localize(None)
    return df.pivot(index='Date',columns='Ticker',values='residual_mom_score_tradable').reindex(index=index,columns=columns)
def build(prices,ggg,program):
    signal=residual_momentum_signal(prices); raw=top_five_weights(signal,prices); vol=volatility_manage(raw,prices); sources={'raw':raw,'vol_managed':vol}; candidates={'benchmark':ggg}
    for name,d in program['candidates'].items(): candidates[name]=sources[d['source']] if d['kind']=='standalone' else blend_with_ggg(ggg,sources[d['source']],float(d['blend_weight']))
    return signal,sources,candidates

def main():
    p=json.loads(PROGRAM.read_text()); assert len(p['candidates'])==p['selection_budget']; manifest_ok=verify_manifest(); assert sha256(SAVED_SIGNAL)==SAVED_SIGNAL_SHA256
    prices=read_dated_csv(SOURCE/'data/01_data_hub/weekly_prices.csv').apply(pd.to_numeric,errors='coerce'); forward=next_week_returns(prices); ggg=run_from_artifacts(SOURCE,causal_training=True).stages['final_etf_weights']
    signal,sources,candidates=build(prices,ggg,p); saved=saved_signal_panel(prices.index,prices.columns); signal_error=frame_difference(signal,saved); signal_missing_mismatch=int((signal.isna()!=saved.isna()).sum().sum())
    _,_,second=build(prices,ggg,p); deterministic=pd.DataFrame([{'candidate':n,'first_hash':frame_hash(candidates[n]),'second_hash':frame_hash(second[n]),'hash_equal':frame_hash(candidates[n])==frame_hash(second[n]),'maximum_difference':frame_difference(candidates[n],second[n])} for n in p['candidates']])
    perf=[]; returns={}
    for n,w in candidates.items():
        for cost in p['cost_bps']:
            path=portfolio_path(w,forward,float(cost));
            if cost==50: returns[n]=path.net_return
            windows={'full':path.net_return,'recent_3y':path.loc[path.index>=path.index.max()-pd.DateOffset(years=3),'net_return'],'post_2024':path.loc[path.index>=pd.Timestamp(p['secondary_window_start']),'net_return']}
            for window,r in windows.items(): perf.append({'candidate':n,'cost_bps':cost,'window':window,**metrics(r)})
    perf=pd.DataFrame(perf); correlations=pd.DataFrame([{'source':s,'candidate':f'residual_momentum_{s}_standalone','full_correlation_to_ggg_50bps':corr(returns[f'residual_momentum_{s}_standalone'],returns['benchmark']),'recent_3y_correlation_to_ggg_50bps':corr(returns[f'residual_momentum_{s}_standalone'].loc[returns[f'residual_momentum_{s}_standalone'].index>=returns[f'residual_momentum_{s}_standalone'].index.max()-pd.DateOffset(years=3)],returns['benchmark'])} for s in sources])
    prefix=[]
    for cut in p['prefix_cutoffs']:
        cutoff=pd.Timestamp(cut); loc=prices.index.get_loc(cutoff)+1; shocked=prices.copy(); shocked.iloc[loc]*=pd.Series([1.4 if i%2==0 else .6 for i in range(len(prices.columns))],index=prices.columns); shocked_ggg=run_from_artifacts(SOURCE,prices_override=shocked,causal_training=True).stages['final_etf_weights']; _,_,alt=build(shocked,shocked_ggg,p)
        for n in p['candidates']: prefix.append({'candidate':n,'cutoff':cut,'shocked_date':str(prices.index[loc].date()),'maximum_prefix_difference':frame_difference(candidates[n].loc[:cutoff],alt[n].loc[:cutoff])})
    prefix=pd.DataFrame(prefix)
    def row(n,w,c): return perf[(perf.candidate==n)&(perf.window==w)&(perf.cost_bps==c)].iloc[0]
    common=p['common_gates']; sg=p['standalone_gates']; source_rows=[]; standalone={}
    for s in sources:
        n=f'residual_momentum_{s}_standalone'; recent=row(n,'recent_3y',50); full100=row(n,'full',100); co=float(correlations.loc[correlations.source==s,'full_correlation_to_ggg_50bps'].iloc[0]); mp=float(prefix.loc[prefix.candidate==n,'maximum_prefix_difference'].max())
        checks={'signal_equivalence_gate':signal_error<=common['maximum_signal_equivalence_error'] and signal_missing_mismatch==0,'recent_return_gate':recent.cagr>=sg['minimum_recent_3y_50bps_cagr'],'full_100bps_gate':full100.cagr>=sg['minimum_full_100bps_cagr'],'correlation_gate':abs(co)<=sg['maximum_abs_full_correlation_to_ggg'],'drawdown_gate':abs(recent.max_drawdown)<=sg['maximum_recent_3y_drawdown_magnitude'],'prefix_gate':mp<=common['maximum_prefix_absolute_difference'],'determinism_gate':bool(deterministic.loc[deterministic.candidate==n,'hash_equal'].all()),'manifest_gate':manifest_ok}; standalone[s]=all(checks.values()); source_rows.append({'source':s,'candidate':n,'recent_3y_50bps_cagr':recent.cagr,'full_100bps_cagr':full100.cagr,'full_correlation_to_ggg':co,'recent_3y_50bps_sharpe':recent.sharpe_zero_rf,'recent_3y_50bps_max_drawdown':recent.max_drawdown,**checks,'standalone_qualified':all(checks.values())})
    source_q=pd.DataFrame(source_rows); bg=p['blend_gates']; bench={w:row('benchmark',w,50) for w in ['full','recent_3y','post_2024']}; blends=[]
    for n,d in p['candidates'].items():
        if d['kind']!='blend': continue
        obs={w:row(n,w,50) for w in bench}; mp=float(prefix.loc[prefix.candidate==n,'maximum_prefix_difference'].max()); checks={'parent_source_gate':standalone[d['source']],'recent_cagr_gate':obs['recent_3y'].cagr-bench['recent_3y'].cagr>=bg['minimum_recent_3y_50bps_cagr_improvement'],'post_2024_gate':obs['post_2024'].cagr-bench['post_2024'].cagr>=bg['minimum_post_2024_50bps_cagr_improvement'],'full_cagr_gate':obs['full'].cagr-bench['full'].cagr>=-bg['maximum_full_50bps_cagr_degradation'],'drawdown_gate':abs(obs['recent_3y'].max_drawdown)<=bg['maximum_recent_3y_drawdown_magnitude'],'prefix_gate':mp<=common['maximum_prefix_absolute_difference'],'determinism_gate':bool(deterministic.loc[deterministic.candidate==n,'hash_equal'].all()),'manifest_gate':manifest_ok}; blends.append({'candidate':n,'source':d['source'],'blend_weight':d['blend_weight'],'recent_3y_50bps_cagr':obs['recent_3y'].cagr,'recent_cagr_improvement':obs['recent_3y'].cagr-bench['recent_3y'].cagr,'post_2024_cagr_improvement':obs['post_2024'].cagr-bench['post_2024'].cagr,'full_cagr_improvement':obs['full'].cagr-bench['full'].cagr,'recent_3y_50bps_sharpe':obs['recent_3y'].sharpe_zero_rf,'recent_3y_50bps_max_drawdown':obs['recent_3y'].max_drawdown,**checks,'blend_qualified':all(checks.values())})
    blend_q=pd.DataFrame(blends).sort_values('recent_3y_50bps_cagr',ascending=False); shortlist=blend_q.loc[blend_q.blend_qualified,'candidate'].tolist(); OUTPUT.mkdir(parents=True,exist_ok=True)
    perf.to_csv(OUTPUT/'performance.csv',index=False); correlations.to_csv(OUTPUT/'correlations.csv',index=False); prefix.to_csv(OUTPUT/'prefix_invariance.csv',index=False); deterministic.to_csv(OUTPUT/'determinism.csv',index=False); source_q.to_csv(OUTPUT/'source_qualification.csv',index=False); blend_q.to_csv(OUTPUT/'blend_qualification.csv',index=False); pd.DataFrame([{'maximum_signal_error':signal_error,'missingness_mismatches':signal_missing_mismatch,'passed':signal_error<=common['maximum_signal_equivalence_error'] and signal_missing_mismatch==0}]).to_csv(OUTPUT/'signal_equivalence.csv',index=False)
    best=blend_q.iloc[0]; result={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'program':p['program'],'program_sha256':sha256(PROGRAM),'module_sha256':sha256(MODULE),'manifest_sha256':sha256(MANIFEST),'snapshot_hashes_verified':manifest_ok,'signal_maximum_difference':signal_error,'signal_missingness_mismatches':signal_missing_mismatch,'standalone_sources_qualified':[s for s,x in standalone.items() if x],'research_blend_shortlist':shortlist,'maximum_prefix_difference':float(prefix.maximum_prefix_difference.max()),'all_deterministic':bool(deterministic.hash_equal.all()),'benchmark_recent_3y_50bps_cagr':bench['recent_3y'].cagr,'decision':'retain_residual_momentum_blends' if shortlist else 'residual_momentum_source_rejected','promoted_to_production':False,'live_trading_enabled':False}; arts=['performance.csv','correlations.csv','prefix_invariance.csv','determinism.csv','source_qualification.csv','blend_qualification.csv','signal_equivalence.csv']; result['artifacts']={n:{'sha256':sha256(OUTPUT/n),'bytes':(OUTPUT/n).stat().st_size} for n in arts}; (OUTPUT/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    (OUTPUT/'report.md').write_text('\n'.join(['# Independent residual-momentum source — Batch 50','',f"Raw signal maximum difference versus the saved audit comparator: {signal_error:.3e}; missingness mismatches: {signal_missing_mismatch}. Snapshot hashes verified: **{manifest_ok}**; maximum prefix difference: {result['maximum_prefix_difference']:.3e}; all deterministic: **{result['all_deterministic']}**.",'',f"Qualified standalone sources: {', '.join(result['standalone_sources_qualified']) if result['standalone_sources_qualified'] else 'none'}. Best blend `{best.candidate}` produced recent-three-year CAGR {best.recent_3y_50bps_cagr:.2%} versus {bench['recent_3y'].cagr:.2%}, improvement {best.recent_cagr_improvement:.2%}.",'',f"Qualified blend shortlist: {', '.join(shortlist) if shortlist else 'none'}. No production promotion from observed history.",'']))
    print(json.dumps({'signal_error':signal_error,'standalone_qualified':result['standalone_sources_qualified'],'shortlist':shortlist,'best_blend':best.candidate,'best_recent_cagr':best.recent_3y_50bps_cagr,'benchmark':bench['recent_3y'].cagr},indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
