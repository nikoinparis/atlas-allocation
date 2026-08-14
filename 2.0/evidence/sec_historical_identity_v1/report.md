# SEC historical identity audit v1

The SEC filing roster contains **1,281** technology/energy CIKs. Current SEC mapping resolves 573; explicit symbols from the last eligible inline filing resolve 247; and standalone legacy XBRL resolves another 193. **268** remain unresolved.

After excluding multiple-symbol identities and symbols assigned to overlapping CIK histories, **947** CIKs are eligible for a free-price coverage probe. Coverage is 93.0% at the latest decision, never below 92.3% from 2023 onward, and reaches a full-history minimum of 64.8%.

This authorizes only a price-availability and issuer-identity probe. It does not authorize a strategy backtest. The remaining blockers are historical ticker changes, ticker reuse, delisting returns, and explicit treatment of unresolved companies.
