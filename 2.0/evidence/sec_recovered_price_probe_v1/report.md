# Recovered-symbol free-price probe v1

Yahoo returned histories for **89 of 416** usable SEC-recovered former-company symbols (21.4%). Only **58** histories overlap the corresponding issuer's eligible SEC period (13.9%); non-overlapping histories are treated as possible ticker reuse, not valid observations.

Even under the optimistic assumption that every current SEC ticker has valid history, total universe coverage falls as low as **75.2%** from 2023 onward. Yahoo also supplies no complete delisting-return table. A survivorship-safe strategy backtest is therefore blocked; failed symbols must not be silently deleted.
