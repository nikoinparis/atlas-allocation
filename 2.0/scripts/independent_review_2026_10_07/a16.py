import numpy as np, pandas as pd, yfinance as yf
px=pd.read_csv('etf_prices.csv',index_col=0,parse_dates=True)
live=yf.download(['DBMF','KMLM'],start='2019-01-01',end='2026-10-07',auto_adjust=True,progress=False)['Close']
m=pd.concat([px,live],axis=1).resample('ME').last().pct_change()
d=pd.read_excel('tsmom.xlsx','TSMOM Factors',header=None)
hdr=17; t=d.iloc[hdr+1:,:6]; t.columns=['date','TSMOM','CM','EQ','FI','FX']
t['date']=pd.to_datetime(t['date'],errors='coerce'); t=t.dropna(subset=['date']).set_index('date').astype(float)
t.index=t.index.to_period('M').to_timestamp('M')
m.index=m.index.to_period('M').to_timestamp('M')
rf=m['BIL'].where(m.index>='2007-07-31', m['SHY'])
FEE=0.01/12
def fund(ex): return rf+ex-FEE
blend=(m[['SPY','GLD','SHY']].mean(axis=1))  # monthly rebalanced equal thirds
def port(sleeve, w=0.2, bps=10):
    # monthly rebalance; traded weight approximated by drift of the two parts within the month
    a=blend; b=sleeve; r=(1-w)*a+w*b
    drift=(w*(1-w)*(b-a)).abs()/(1+r)  # weight drift of sleeve over the month
    return r-2*drift*bps/1e4
def blend_cost(bps):
    sub=m[['SPY','GLD','SHY']]; r=sub.mean(axis=1)
    tov=((sub.sub(r,axis=0)).abs().sum(axis=1)/3)/(1+r)
    return r-tov*bps/1e4
def st(r):
    r=r.dropna(); w=(1+r).cumprod(); y=len(r)/12
    ex=r-rf.reindex(r.index)
    return dict(CAGR=w.iloc[-1]**(1/y)-1, Sharpe=ex.mean()/ex.std()*np.sqrt(12), maxDD=(w/w.cummax()-1).min(), vol=r.std()*np.sqrt(12), n=len(r))
def fmt(s): return f"CAGR {s['CAGR']:6.2%} Sharpe {s['Sharpe']:5.2f} maxDD {s['maxDD']:7.2%} vol {s['vol']:5.1%} n={s['n']}"
W=slice('2013-01-31','2026-05-31')
tf=fund(t['TSMOM'])
B=blend_cost(10); P=(1-0.2)*0+port(tf)  # P already includes blend at 0 cost; add blend cost
P=port(tf)-(blend-B)*0.8
print("DECISION WINDOW 2013-01..2026-05")
sB,sP=st(B[W]),st(P[W]); print(" blend      ",fmt(sB)); print(" 80/20 trend",fmt(sP)); print(" trend fund ",fmt(st(tf[W])))
dS=sP['Sharpe']-sB['Sharpe']
# block bootstrap of Sharpe difference
rng=np.random.default_rng(0); xb=(B[W]-rf[W]).values; xp=(P[W]-rf[W]).values; n=len(xb); L=12; k=int(np.ceil(n/L)); D=[]
for _ in range(5000):
    st_=rng.integers(0,n-L+1,k); idx=np.concatenate([np.arange(s,s+L) for s in st_])[:n]
    D.append(xp[idx].mean()/xp[idx].std()*np.sqrt(12)-xb[idx].mean()/xb[idx].std()*np.sqrt(12))
D=np.array(D); p=np.mean((D-D.mean())>=dS)  # null centred at zero
print(f" Sharpe diff {dS:+.3f}  bootstrap p {p:.3f}  -> PASS={dS>=0.05 and p<0.05}")
# alpha
for nm,bench in [('SPY',m['SPY']),('blend',blend)]:
    y=(tf-rf)[W]; xx=(bench-rf)[W]; ok=y.notna()&xx.notna(); y,xx=y[ok].values,xx[ok].values
    X=np.column_stack([np.ones(len(y)),xx]); b=np.linalg.lstsq(X,y,rcond=None)[0]; e=y-X@b
    S=np.zeros((2,2)); 
    for l in range(7):
        w=1 if l==0 else 1-l/7; G=(X[l:]*e[l:,None]).T@(X[:len(y)-l]*e[:len(y)-l,None]); S+=w*(G if l==0 else G+G.T)
    XtXi=np.linalg.inv(X.T@X); V=XtXi@S@XtXi; tval=b[0]/np.sqrt(V[0,0])
    print(f" trend alpha vs {nm}: {b[0]*12:+.2%}/yr NW t={tval:.2f} beta={b[1]:+.2f} corr={np.corrcoef(y,xx)[0,1]:+.2f}")
print("COST GRID (decision window)")
for bps in (0,10,50,100):
    Bc=blend_cost(bps); Pc=port(tf,bps=bps)-(blend-Bc)*0.8
    print(f" {bps:>3}bps blend {fmt(st(Bc[W]))} | 80/20 {fmt(st(Pc[W]))}")
print("WINDOWS (total return): blend vs 80/20 vs trend fund")
for a,b in [('2008-01','2009-12'),('2020-01','2020-12'),('2022-01','2022-12'),('2023-01','2026-05'),('2005-01','2012-12')]:
    f=lambda r:(1+r[a:b]).prod()-1
    print(f" {a}..{b}: {f(B):+.1%} vs {f(P):+.1%} vs {f(tf):+.1%}   Sharpe {st(B[a:b])['Sharpe']:.2f} vs {st(P[a:b])['Sharpe']:.2f}")
print("LEAVE-ONE-ASSET-CLASS-OUT (decision window)")
for drop in ['CM','EQ','FI','FX']:
    keep=[c for c in ['CM','EQ','FI','FX'] if c!=drop]; s=fund(t[keep].mean(axis=1)); Pl=port(s)-(blend-B)*0.8
    print(f" drop {drop}: 80/20 Sharpe {st(Pl[W])['Sharpe']:.2f} (blend {sB['Sharpe']:.2f})  sleeve alone {fmt(st(s[W]))}")
print("LIVE ETFs (descriptive)")
for e,start in [('DBMF','2019-06-30'),('KMLM','2021-01-31')]:
    LW=slice(start,'2026-09-30'); Pe=port(m[e])-(blend-B)*0.8
    print(f" {e}: alone {fmt(st(m[e][LW]))}\n       blend {fmt(st(B[LW]))}\n       80/20 {fmt(st(Pe[LW]))}  corr to SPY {m[e][LW].corr(m['SPY'][LW]):+.2f}")
    a=st(tf['2019-06':'2026-05']) if e=='DBMF' else None
print(" AQR factor-fund over DBMF window:",fmt(st(tf['2019-07-31':'2026-05-31'])), " corr with DBMF", tf['2019-07':'2026-05'].corr(m['DBMF']['2019-07':'2026-05']).round(2))
