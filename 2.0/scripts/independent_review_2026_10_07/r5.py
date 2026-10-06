import numpy as np, pandas as pd
px=pd.read_csv('etf_prices.csv',index_col=0,parse_dates=True)
dr=px.pct_change()
# T-bill proxy: BIL from 2007-06, before that SHY (conservative; slightly overstates rf)
rf=dr['BIL'].where(dr.index>='2007-06-01', dr['SHY']).fillna(0)
# global equity: VT from 2008-07, before that 60 SPY/40 EFA
veq=dr['VT'].where(dr.index>='2008-07-01', 0.6*dr['SPY']+0.4*dr['EFA'])
dr['GEQ']=veq
def run(w, bps, start='2005-01-03', end='2026-09-30'):
    r=dr.loc[start:end, list(w)].fillna(0); wt=pd.Series(w)
    cur=wt.copy(); out=[]; tov=0; me=r.index.to_series().groupby(r.index.to_period('M')).max()
    mends=set(me.values)
    for t,row in r.iterrows():
        pr=(cur*row).sum(); out.append(pr)
        cur=cur*(1+row)/(1+pr)
        if t in mends:
            trade=(cur-wt).abs().sum(); tov+=trade; out[-1]-=trade*bps/1e4; cur=wt.copy()
    s=pd.Series(out,index=r.index); return s, tov/((r.index[-1]-r.index[0]).days/365.25)
def st(s):
    w=(1+s).cumprod(); y=len(s)/252
    cagr=w.iloc[-1]**(1/y)-1; vol=s.std()*np.sqrt(252)
    ex=(s-rf.reindex(s.index)).mean()*252/vol; raw=s.mean()*252/vol
    return cagr, ex, raw, (w/w.cummax()-1).min(), vol
def tot(s,a,b): x=s.loc[a:b]; return (1+x).prod()-1
P={'SPY 100':{'SPY':1},'SPY/IEF 60/40':{'SPY':.6,'IEF':.4},'SPY/GLD/SHY thirds':{'SPY':1/3,'GLD':1/3,'SHY':1/3},'GlobalEq60/IEF20/GLD20':{'GEQ':.6,'IEF':.2,'GLD':.2}}
for name,w in P.items():
    print(f"\n{name}")
    for bps in (0,10,50,100):
        s,to=run(w,bps); c,ex,raw,dd,vol=st(s)
        print(f"  {bps:>3}bps CAGR {c:6.2%} Sharpe ex-rf {ex:.2f} raw {raw:.2f} maxDD {dd:7.2%} vol {vol:.1%} turnover/yr {to:.2f}")
    s,_=run(w,10)
    print("  windows @10bps: GFC 07-10..09-03 %+.1f%% | 2020 Feb-Mar %+.1f%% | 2022 %+.1f%% | 2005-15 CAGR %.1f%% | 2016-26 %.1f%% | 2023-01..2025-04-03 %.1f%% | 2025-04-04.. %.1f%%" % tuple(100*v for v in (
      tot(s,'2007-10-09','2009-03-09'),tot(s,'2020-02-19','2020-03-23'),tot(s,'2022-01-01','2022-12-31'),
      st(s.loc['2005':'2015'])[0],st(s.loc['2016':'2026'])[0],st(s.loc['2023-01-01':'2025-04-03'])[0],st(s.loc['2025-04-04':])[0])))
    print("  Sharpe ex-rf by window: 2005-15 %.2f | 2016-26 %.2f | 2008-09 %.2f | 2023-26 %.2f" % (st(s.loc['2005':'2015'])[1],st(s.loc['2016':'2026'])[1],st(s.loc['2008':'2009'])[1],st(s.loc['2023':'2026'])[1]))
