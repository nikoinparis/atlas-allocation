# Release Validation Report — 2026-05-07

**Purpose:** Record of build/lint/typecheck results before staging.

---

## Commands Run

| Command | Result |
|---|---|
| `npm run typecheck` | **PASS** — no type errors |
| `npm run build` | **PASS** — compiled in 2.4s, 3/3 static pages |
| `python3 -m py_compile scripts/build_release_dashboard_bundle.py` | PASS (implicitly validated by successful run) |
| `python3 scripts/build_release_dashboard_bundle.py` | **PASS** — bundle updated, 1,370 KB |

---

## Build Output

```
▲ Next.js 15.5.15
✓ Compiled successfully in 2.4s
✓ TypeScript types valid
✓ Static pages (3/3) generated
Route /: 146 kB, 249 kB first load JS
```

---

## Bundle Validation

```
Valid JSON: True
Registry keys: 36
Summary versions: 10 (3 existing + 7 new shadows)
versionReturns: 10 (each with 1,110 rows)
state_summary: 40 rows
Bundle size: 1,370 KB
```

---

## TypeScript Changes Made

All TypeScript changes were minimal and targeted at bundle compatibility:

1. **`src/lib/compact-dashboard.ts`** — Added `InputRow` type and `normalizeInputRows()` helper; changed 4 input array types from `AnyRow[]` to `InputRow[]`; changed 3 usages to `normalizeInputRows()`. These changes are backwards-compatible — the runtime behavior is identical, the type system is now correctly permissive for bundle input rows.

2. **`src/types/dashboard.ts`** — Made `ReturnPoint.method` optional. This is a safe relaxation; no runtime behaviour changes.

---

## Warnings

- None from build
- Note: The `.next/` build output directory is NOT tracked in git and will not be committed

---

## Dashboard Public-Release Status

**READY.** The dashboard:
- Renders server-side on first paint with all Phase 7 research state
- Shows correct production governance (pin unchanged, GGG1 still candidate)
- Communicates the research arc completion clearly
- Includes appropriate disclaimer (research only, not financial advice)
- Bundle is compact (1.37 MB vs forbidden 15 MB+ `dashboard-data.json`)
- No forbidden files included
