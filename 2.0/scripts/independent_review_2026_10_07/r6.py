import numpy as np, pandas as pd
from scipy.stats import spearmanr
rng=np.random.default_rng(1)
def sim(ic,N,T,R=2000,sd=0.10):
    full=np.empty(R); mid=np.empty(R)
    for k in range(R):
        dec=np.zeros(10)
        for t in range(T):
            z=rng.standard_normal(N); e=rng.standard_t(4,N)/np.sqrt(2)
            it=np.clip(ic+sd*rng.standard_normal(),-0.9,0.9); r=it*z+np.sqrt(1-it**2)*e
            q=np.argsort(np.argsort(z))*10//N
            dec+=np.bincount(q,weights=r,minlength=10)/np.bincount(q,minlength=10)
        full[k]=spearmanr(np.arange(10),dec)[0]; mid[k]=spearmanr(np.arange(8),dec[1:9])[0]
    within=np.mean(np.abs(full)<=0.17); passes=np.mean((full>0.5)&(mid>0.5))
    return np.median(full), within, passes
for ic,N,T in [(0.03,300,14),(0.03,300,39),(0.03,2000,39),(0.05,300,14),(0.0,300,14),(0.0,2000,39)]:
    m,w,p=sim(ic,N,T)
    print(f"IC {ic:.2f} N={N:4d} T={T:2d}: median mono {m:+.2f}  P(|mono|<=0.17) {w:.2f}  P(passes 0.5 bar) {p:.2f}")
