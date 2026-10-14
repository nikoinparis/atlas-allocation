# Fresard-Hoberg-Phillips VTNIC, 10% granularity (Step 357, queue A21)

- Source: https://faculty.marshall.usc.edu/Gerard-Hoberg/FresardHobergPhillipsDataSite/idata/VertNetwork_10gran.zip
- Downloaded 2026-10-14 in 24 ranged parts (server ~40KB/s per connection), assembled, `unzip -t` clean.
  sha256 42430b414d097587526b7794cb7232565f962be1b436941bec9e2507354d1ad1 (854,396,826 bytes)
- Member VertNetwork_10gran.txt (3.1GB, Deflate64: Python zipfile cannot read it; stream with `unzip -p`).
  Columns year, gvkey1, gvkey2, vertscore; DIRECTED (gvkey1 upstream of gvkey2); 1989-2021; not lagged; self rows blank.
- Cite Fresard, Hoberg & Phillips, RFS 2020.
