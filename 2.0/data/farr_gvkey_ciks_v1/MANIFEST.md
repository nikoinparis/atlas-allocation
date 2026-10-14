# farr gvkey_ciks link table (Step 354, queue B16)

- Source: CRAN farr 1.0.1, https://cran.r-project.org/src/contrib/farr_1.0.1.tar.gz (Ian Gow, MIT licence)
- sha256 farr_1.0.1.tar.gz 5f9cad6d0fde94114e7b2e241b449c4627410b5c013471e650b617a29523a2d0
- Extracted farr/data/gvkey_ciks.rda with Rscript --vanilla (load into an environment, write.csv) to
  gvkey_ciks.csv.gz: 48,517 rows, gvkey, iid, cik, first_date (1993-08-13..2025-08-14),
  last_date (1994-01-14..2025-08-29). Provenance of the link dates is not documented on the package page.
- Measured use: maps TNIC gvkeys to 86-93% of the liquid price-panel universe per year, 2012-2025.
