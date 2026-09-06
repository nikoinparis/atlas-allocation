# SEC historical identity audit v1

The SEC filing roster contains **1,285** technology/energy CIKs. Current SEC mapping resolves 577; explicit symbols from the last eligible inline filing resolve 247; and standalone legacy XBRL resolves another 193. **268** remain unresolved.

After excluding multiple-symbol identities and symbols assigned to overlapping CIK histories, **952** CIKs are eligible for a free-price coverage probe. Coverage is 93.1% at the latest decision, never below 92.5% from 2023 onward, and reaches a full-history minimum of 65.0%.

This authorizes only a price-availability and issuer-identity probe. It does not authorize a strategy backtest. The remaining blockers are historical ticker changes, ticker reuse, delisting returns, and explicit treatment of unresolved companies.
