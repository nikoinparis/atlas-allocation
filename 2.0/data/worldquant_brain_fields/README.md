# WorldQuant BRAIN field dictionaries

Downloaded with:

```
python ../../scripts/run_worldquant_brain_decile_ladder_v1.py --list-datasets
python ../../scripts/run_worldquant_brain_decile_ladder_v1.py --dump-fields <dataset_id>
```

One CSV per dataset: `id, description, type, coverage, userCount, alphaCount`.

Committed on purpose. The web UI paginates the fundamental dataset across ~45 pages, which
is not a reference anyone can work from, and an unknown field id has already cost one round
of simulations (`net_income` was rejected on 2026-09-22). Having the dictionary on disk
means field ids stop blocking future sessions.

**Read `coverage` before building on any field.** Below 50% a signal cannot be read on
deciles at all — most of the cross-section becomes ties and the monotonicity number is
uninterpretable rather than low. Step 298 nearly reported a discovery on a signal that was
93.3% zeros.

These describe WorldQuant's data, which is theirs. Nothing here is their data — only the
names, descriptions and coverage of the fields.
