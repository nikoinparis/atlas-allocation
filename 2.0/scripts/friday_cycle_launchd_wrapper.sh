#!/bin/zsh
# launchd entry point for the Friday forward cycle.
#
# Between 2026-10-11 and 2026-10-12 the checkout was switched to a `main` 75 commits
# behind origin/main. run_full_friday_cycle_v1.py did not exist there, Python failed
# before --notify could fire, and the job failed silently twice a day. This wrapper makes
# that failure loud and fixes the harmless case:
#
#   HEAD already contains origin/main      -> run.
#   HEAD is strictly behind origin/main    -> fast-forward (never a reset), then run.
#   HEAD has diverged from origin/main     -> do NOT run; notify and exit 3.

REPO="/Users/nicholasturangan/Projects/Portfolio Optimizer"
GIT=/usr/bin/git

notify() {
  /usr/bin/osascript -e "display notification \"$1\" with title \"Portfolio Optimizer clock\"" >/dev/null 2>&1
  echo "$(date -u +%FT%TZ) $1"
}

cd "$REPO" || { notify "Friday clock NOT run: repo missing"; exit 3; }
$GIT fetch -q origin main || notify "Friday clock: git fetch failed, running on local state"
branch=$($GIT rev-parse --abbrev-ref HEAD)

if ! $GIT merge-base --is-ancestor origin/main HEAD; then
  if $GIT merge-base --is-ancestor HEAD origin/main && $GIT merge -q --ff-only origin/main; then
    echo "$(date -u +%FT%TZ) fast-forwarded $branch to origin/main"
  else
    notify "Friday clock NOT run: checkout ($branch) has diverged from origin/main. Switch to an up-to-date branch."
    exit 3
  fi
fi

if [ ! -f 2.0/scripts/run_full_friday_cycle_v1.py ]; then
  notify "Friday clock NOT run: run_full_friday_cycle_v1.py missing on $branch"
  exit 3
fi

cd 2.0 && exec ./.venv/bin/python scripts/run_full_friday_cycle_v1.py --commit --notify --push
