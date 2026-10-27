#!/usr/bin/env bash
# Prefer strict pooled reports. Recover individual shards only before pooled results exist.
set -euo pipefail
export GH_REPO="herschelruskin/urza-state-solver"
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
mkdir -p benchmark_results
for tick in $(seq 1 46); do
  echo "===== ASSERTIVE CARD RANKING TICK $tick ====="
  rm -rf imported/shards20 imported/shards41 imported/report20 imported/report41
  mkdir -p imported/shards20 imported/shards41 imported/report20 imported/report41
  n20=$(gh api "repos/$GH_REPO/actions/runs/40444150025/artifacts?per_page=100" --jq '[.artifacts[] | select(.name|startswith("dack-assertive-ramp-screen-shard-"))] | length')
  n41=$(gh api "repos/$GH_REPO/actions/runs/40445020227/artifacts?per_page=100" --jq '[.artifacts[] | select(.name|startswith("dack-assertive-flexslots-shard-"))] | length')
  echo "Completed artifact archives: 20-arm $n20/64; 41-arm $n41/64"
  OPTS=""
  nreport20=$(gh api "repos/$GH_REPO/actions/runs/40444150025/artifacts?per_page=100" --jq '[.artifacts[] | select(.name=="dack-assertive-ramp-screen-n256-report")] | length')
  if [ "$nreport20" -gt 0 ]; then
    gh run download 40444150025 --repo "$GH_REPO" \
      --name dack-assertive-ramp-screen-n256-report --dir imported/report20
    OPTS="$OPTS --screen20-report imported/report20/dack_assertive_ramp_land_key_screen_n256_report.json"
    OPTS="$OPTS --screen20-raw imported/report20/dack_assertive_ramp_land_key_screen_n256_report.raw.json.gz"
  fi
  if [ "$nreport20" -eq 0 ] && [ "$n20" -gt 0 ]; then
    gh run download 40444150025 --repo "$GH_REPO" \
      --pattern 'dack-assertive-ramp-screen-shard-*' --dir imported/shards20
  fi
  nreport41=$(gh api "repos/$GH_REPO/actions/runs/40445020227/artifacts?per_page=100" --jq '[.artifacts[] | select(.name=="dack-assertive-flexslots-n128-validated-report")] | length')
  if [ "$nreport41" -eq 0 ] && [ "$n41" -gt 0 ]; then
    gh run download 40445020227 --repo "$GH_REPO" \
      --pattern 'dack-assertive-flexslots-shard-*' --dir imported/shards41
  fi
  if [ "$nreport41" -gt 0 ]; then
    gh run download 40445020227 --repo "$GH_REPO" \
      --name dack-assertive-flexslots-n128-validated-report --dir imported/report41
    OPTS="$OPTS --flex41-report imported/report41/dack_assertive_flexslots_33to36_n128_report.json"
    OPTS="$OPTS --flex41-raw imported/report41/dack_assertive_flexslots_33to36_n128_report.raw.json.gz"
  fi
  # Deliberate unquoted expansion: OPTS is built only from fixed code-owned paths.
  python -u dack_assertive_ramp_live_leaderboard.py \
    --screen20-shards imported/shards20 --flex41-shards imported/shards41 $OPTS \
    --json-out benchmark_results/dack_assertive_ramp_card_tracker.json \
    --md-out DACK_ASSERTIVE_RAMP_CARD_LEADERBOARD.md
  git add -f benchmark_results/dack_assertive_ramp_card_tracker.json DACK_ASSERTIVE_RAMP_CARD_LEADERBOARD.md
  if ! git diff --cached --quiet; then
    git commit -m "Update partial Assertive ramp ranks ($n20/64 and $n41/64 shard sets)"
    git pull --rebase
    git push
  fi
  if [ "$nreport20" -gt 0 ] && [ "$nreport41" -gt 0 ]; then
    echo "Both official strict pooled reports ingested: complete"; break
  fi
  status20=$(gh api "repos/$GH_REPO/actions/runs/40444150025" --jq '.status')
  status41=$(gh api "repos/$GH_REPO/actions/runs/40445020227" --jq '.status')
  if [ "$status20" = completed ] && [ "$status41" = completed ]; then
    echo "Both input runs ended; available evidence was saved"; break
  fi
  if [ "$tick" -lt 46 ]; then sleep 420; fi
done

# Re-run following validated completion of both source screens on 2026-10-27.
