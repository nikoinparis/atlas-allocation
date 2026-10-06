import numpy as np, pandas as pd
px=pd.read_csv('etf_prices.csv',index_col=0,parse_dates=True)
r=px[['SPY','BIL','SHY']].pct_change().loc['2000-01-01':'2026-09-30']
rf=r['BIL'].where(r.index>='2007-06-01', r['SHY']).fillna(0); spy=r['SPY']
ym=r.index.to_period('M'); pos=pd.Series(r.index).groupby(ym).cumcount().values
cnt=pd.Series(r.index).groupby(ym).transform('size').values
flag=pd.Series((pos<3)|(pos==cnt-1),index=r.index)  # first 3 days + last day
def run(fl,bps,legs=2):
    fl=fl.astype(float); sw=fl.diff().abs().fillna(fl.iloc[0])
    return fl*spy+(1-fl)*rf - sw*legs*bps/1e4
def st(x):
    w=(1+x).cumprod(); y=len(x)/252; ex=x-rf.reindex(x.index)
    return dict(CAGR=w.iloc[-1]**(1/y)-1,Sh=ex.mean()/x.std()*np.sqrt(252),DD=(w/w.cummax()-1).min())
f=lambda s:f"CAGR {s['CAGR']:6.2%} Sharpe {s['Sh']:5.2f} maxDD {s['DD']:7.2%}"
W=slice('2006-01-01','2026-09-30')
expo=flag[W].mean()
def mix(bps):  # constant mix, monthly rebalance; tiny cost
    return expo*spy+(1-expo)*rf
print(f"exposure {expo:.1%}, switches/yr {flag[W].astype(int).diff().abs().sum()/ (len(flag[W])/252):.1f}")
for bps in (0,10,50,100):
    print(f"{bps:>3}bps rule {f(st(run(flag,bps)[W]))} | 1-leg cost {f(st(run(flag,bps,1)[W]))} | null mix {f(st(mix(bps)[W]))}")
R=run(flag,10)[W]; N=mix(10)[W]; sR,sN=st(R),st(N)
# placebo
rng=np.random.default_rng(0); P=[]
idx=r.index; mon=ym
grp=pd.Series(np.arange(len(idx))).groupby(mon.values)
groups=[g.values for _,g in grp]
for k in range(2000):
    fl=np.zeros(len(idx),bool)
    for g in groups:
        if len(g)<4: continue
        s=rng.integers(0,len(g)-3); fl[g[s:s+4]]=True
    P.append(st(run(pd.Series(fl,index=idx),10)[W])['Sh'])
P=np.array(P); p=np.mean(P>=sR['Sh'])
print(f"\nDECISION @10bps (2 legs): rule Sharpe {sR['Sh']:.2f} vs null {sN['Sh']:.2f} (need +0.10); placebo p {p:.3f}; CAGR {sR['CAGR']:.2%} vs {sN['CAGR']:.2%}")
print("PASS =", sR['Sh']>=sN['Sh']+0.10 and p<0.05 and sR['CAGR']>=sN['CAGR'])
R0=run(flag,0)[W]; print(f"@0bps rule Sharpe {st(R0)['Sh']:.2f}, placebo median (10bps) {np.median(P):.2f}")
# share of SPY log return inside window
ls=np.log1p(spy[W]); print(f"share of SPY log return earned in window: {ls[flag[W]].sum()/ls.sum():.1%} (window = {expo:.1%} of days)")
pre=slice('2000-01-01','2005-12-31'); lp=np.log1p(spy[pre]); print(f"context 2000-05: share {lp[flag[pre]].sum()/lp.sum():.1%} (SPY total log {lp.sum():+.3f})")
for a,b in [('2008-01-01','2009-12-31'),('2020-01-01','2020-12-31'),('2022-01-01','2022-12-31'),('2023-01-01','2026-09-30')]:
    tr=lambda x:(1+x[a:b]).prod()-1
    print(f" {a[:7]}..{b[:7]}: rule@10 {tr(run(flag,10)):+.1%} rule@0 {tr(run(flag,0)):+.1%} null {tr(mix(0)):+.1%} SPY {tr(spy):+.1%}")
# drop 5 best windows
wid=(flag[W].astype(int).diff()==1).cumsum()*flag[W]
wr=(np.log1p(R0)).groupby(wid).sum().drop(0,errors='ignore'); best=wr.nlargest(5).index
R0b=R0.copy(); R0b[wid.isin(best)]=rf[W][wid.isin(best)]
print(f"drop 5 best windows @0bps: Sharpe {st(R0b)['Sh']:.2f} CAGR {st(R0b)['CAGR']:.2%}")
