# Incoming immutable packets

Place generated decision and realization packets here only during their valid
Friday snapshot windows. Packet filenames should begin with `decision-` or
`observation-` and end in `.json`.

The forward recorder verifies the packet hash, source-manifest hash, protocol
version, point-in-time cutoff, Friday window, chronology, and held-security
returns before appending evidence. A rejected or missed packet must not be
rewritten later to backfill the clock.
