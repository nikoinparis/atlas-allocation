import json, numpy as np, pandas as pd
D="/Users/nicholasturangan/Projects/Portfolio Optimizer/2.0/dashboard/public/return-first-dashboard.json"
d=json.load(open(D))
px=pd.read_csv('etf_prices.csv',index_col=0,parse_dates=True)
# weekly Friday closes
wk=px.resample('W-FRI').last()
wret=wk.pct_change()
bil=wret['BIL'].fillna(0)
def stats(r, rf=None, per=52):
    r=r.dropna(); w=(1+r).cumprod()
    cagr=w.iloc[-1]**(per/len(r))-1
    ex=r-(rf.reindex(r.index).fillna(0) if rf is not None else 0)
    sh=ex.mean()/r.std()*np.sqrt(per)
    dd=(w/w.cummax()-1).min()
    return cagr,sh,dd
for s in d['strategies']:
    sid=s['strategy']['id']; conv=None
    rec=pd.DataFrame(s['records']); rec['date']=pd.to_datetime(rec['date']); rec=rec.set_index('date')
    g=rec.grossReturn; to=rec.turnover; c=rec.cost; n=rec.netReturn
    implied_bps=(g-n).sum()/max(to.sum(),1e-9)*1e4
    print(f"\n== {sid}  weeks={len(rec)} {rec.index[0].date()}..{rec.index[-1].date()}  sum turnover={to.sum():.1f} implied cost bps={implied_bps:.1f} cost col sum={c.sum():.4f}")
    # R2 alignment: book dates vs SPY week-ending return at lag
    spy=wret['SPY']
    for lag in (-1,0,1):
        al=spy.shift(-lag).reindex(rec.index)
        print(f"   corr lag{lag:+d}: {n.corr(al):.3f}", end='')
    print()
    # R3 cost grid
    for bps in (0,10,50,100):
        r=g-to*bps/1e4
        cg,sh,dd=stats(r,bil)
        print(f"   {bps:>3}bps CAGR {cg:7.2%} Sharpe(ex-rf) {sh:5.2f} maxDD {dd:7.2%}")
    # R4 best weeks
    srt=n.sort_values(ascending=False)
    for k in (5,10):
        r=n.drop(srt.index[:k]); print(f"   drop best {k} weeks: CAGR {stats(r)[0]:.2%}", end='')
    print()
    # windows
    pre=n[n.index<'2025-04-04']; post=n[n.index>='2025-04-04']
    print(f"   pre-break CAGR {stats(pre,bil)[0]:.2%} Sh {stats(pre,bil)[1]:.2f}; post CAGR {stats(post,bil)[0]:.2%} Sh {stats(post,bil)[1]:.2f}")
    s_id=sid; rec.to_pickle(f'rec_{sid}.pkl')
