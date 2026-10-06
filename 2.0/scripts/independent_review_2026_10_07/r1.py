import numpy as np, pandas as pd, glob
px=pd.read_csv('etf_prices.csv',index_col=0,parse_dates=True)
wk=px.resample('W-FRI').last(); wret=wk.pct_change(); bil=wret['BIL']
rng=np.random.default_rng(0)
for f in sorted(glob.glob('rec_*.pkl')):
    sid=f[4:-4]; rec=pd.read_pickle(f)
    g=rec.grossReturn; to=rec.turnover
    net=g-to*50/1e4   # uniform 50 bps for all books (fixes the cash-conversion zero-cost record)
    fwd = 'cash-conversion' not in sid
    # align: book return for week ending date E
    if fwd: net.index=net.index+pd.Timedelta(days=7)
    df=pd.DataFrame({'b':net,'m':wret['SPY'],'rf':bil}).dropna()
    df=df[df.index>='2005-01-01']
    xb=df.b-df.rf; xm=df.m-df.rf
    # past-only 52w beta (min 26)
    beta=xb.rolling(52,min_periods=26).cov(xm)/xm.rolling(52,min_periods=26).var()
    beta=beta.shift(1)
    a=(xb-beta*xm).dropna()
    def ann(x): return x.mean()*52
    # moving-block bootstrap p (one-sided), block 8
    def boot_p(x,B=5000,L=8):
        x=x.values-x.mean(); n=len(x); k=int(np.ceil(n/L)); m=np.empty(B)
        for i in range(B):
            st=rng.integers(0,n-L+1,k); m[i]=np.concatenate([x[s:s+L] for s in st])[:n].mean()
        return (m>=a.mean()).mean()
    pre=a[a.index<'2025-04-11']; post=a[a.index>='2025-04-11']
    print(f"{sid:45s} n={len(a)} alpha {ann(a):+.1%} p={boot_p(a):.3f} | pre {ann(pre):+.1%} (n={len(pre)}) post {ann(post):+.1%} | mean beta {beta.mean():.2f}")
