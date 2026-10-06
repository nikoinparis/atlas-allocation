import numpy as np, pandas as pd
g=pd.read_csv('gspc_irx.csv',index_col=0,parse_dates=True)
px=pd.read_csv('etf_prices.csv',index_col=0,parse_dates=True)
gr=g['^GSPC'].pct_change(); irx=(g['^IRX']/100/252).reindex(gr.index).ffill().fillna(0)
spy=px['SPY'].pct_change(); cash93=px['BIL'].pct_change().where(px.index>='2007-06-01', px['SHY'].pct_change())
# month-end realised variance on the index (for the target) and on the traded series
def rv(r):
    me=r.groupby(r.index.to_period('M')).apply(lambda x: x.tail(21).var()*252)
    return me
rv_idx=rv(gr.dropna())
target=rv_idx.expanding().median().shift(1)   # previous months only
def build(mkt,cash,rvm,start,end,bps):
    mkt=mkt.loc[start:end]; cash=cash.reindex(mkt.index).fillna(0)
    w_m=(target.reindex(rvm.index)/rvm).clip(upper=1.0).shift(1)  # decided at prior month-end
    per=mkt.index.to_period('M'); w=pd.Series(w_m.reindex(per).values,index=mkt.index)
    first=~per.duplicated(); dw=w.diff().abs().where(first,0).fillna(0)
    rule=w*mkt+(1-w)*cash-dw*bps/1e4
    e=w.mean(); null=e*mkt+(1-e)*cash
    return rule,null,w,cash,mkt
def st(x,cash):
    w=(1+x).cumprod(); y=len(x)/252; ex=x-cash
    return dict(CAGR=w.iloc[-1]**(1/y)-1,Sh=ex.mean()/x.std()*np.sqrt(252),DD=(w/w.cummax()-1).min())
F=lambda s:f"CAGR {s['CAGR']:6.2%} Sharpe {s['Sh']:5.2f} maxDD {s['DD']:7.2%}"
rng=np.random.default_rng(0)
def placebo(mkt,cash,w,obs,B=2000):
    per=mkt.index.to_period('M'); wm=w.groupby(per).first(); out=[]
    for _ in range(B):
        perm=pd.Series(rng.permutation(wm.values),index=wm.index)
        ww=pd.Series(perm.reindex(per).values,index=mkt.index)
        first=~per.duplicated(); dw=ww.diff().abs().where(first,0).fillna(0)
        out.append(st(ww*mkt+(1-ww)*cash-dw*10/1e4,cash)['Sh'])
    return np.mean(np.array(out)>=obs)
res={}
for name,mkt,cash,rvm,a,b in [('PRIMARY SPY 1993-02..2026-09',spy,cash93,rv(spy.dropna()),'1993-02-01','2026-09-30'),
                              ('POST-PUB 2016..2026-09',spy,cash93,rv(spy.dropna()),'2016-01-01','2026-09-30'),
                              ('REPLICATION ^GSPC 1933..1992',gr,irx,rv_idx,'1933-01-01','1992-12-31')]:
    print("\n"+name)
    for bps in (0,10,50,100):
        R,N,w,c,m=build(mkt,cash,rvm,a,b,bps)
        print(f"  {bps:>3}bps rule {F(st(R,c))} | null {F(st(N,c))} | buy&hold {F(st(m,c))}  avg exposure {w.mean():.2f}")
    R,N,w,c,m=build(mkt,cash,rvm,a,b,10); sR,sN=st(R,c),st(N,c)
    p=placebo(m,c,w,sR['Sh']) if 'PRIMARY' in name else float('nan')
    res[name]=(sR['Sh']-sN['Sh'],p); print(f"  @10bps Sharpe diff {sR['Sh']-sN['Sh']:+.3f}  placebo p {p:.3f}")
    if 'PRIMARY' in name:
        for x,y in [('1998-08-01','1998-10-31'),('2000-03-01','2002-10-31'),('2008-01-01','2009-12-31'),('2020-01-01','2020-12-31'),('2022-01-01','2022-12-31'),('2023-01-01','2026-09-30')]:
            tr=lambda s:(1+s[x:y]).prod()-1
            print(f"   {x[:7]}..{y[:7]}: rule {tr(R):+.1%}  null {tr(N):+.1%}  SPY {tr(m):+.1%}")
        Rr,Nr,wr,cr,mr=build(gr,irx,rv_idx,'1987-09-01','1987-12-31',10); print(f"   1987 Sep-Dec (index): rule {(1+Rr).prod()-1:+.1%} buy&hold {(1+mr).prod()-1:+.1%}")
d1,p=res['PRIMARY SPY 1993-02..2026-09']; d2,_=res['POST-PUB 2016..2026-09']; d3,_=res['REPLICATION ^GSPC 1933..1992']
print(f"\nPASS conditions: diff>=0.10 {d1>=0.10} | p<0.05 {p<0.05} | 1933-92 >=0 {d3>=0} | 2016-26 >=0 {d2>=0}  => {'PASS' if (d1>=0.10 and p<0.05 and d3>=0 and d2>=0) else 'FAIL'}")
