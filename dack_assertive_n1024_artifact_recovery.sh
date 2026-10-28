#!/usr/bin/env bash
# Repair GitHub artifact-upload ECONNRESET; same independent original seeds.
set -euo pipefail
export GH_REPO="herschelruskin/urza-state-solver"
export MAIN_RUN=40568784040
export PYTHONHASHSEED=0
mkdir -p shards/recovered shards/official benchmark_results
python -u dack_assertive_protected_auras_heldout_n1024_20261027.py --audit
# Shard 104 ran eight games successfully but GitHub upload failed.
python -u dack_assertive_protected_auras_heldout_n1024_20261027.py \
  --shard 104 --games 8 --out shards/recovered/aura_heldout_shard_104.json.gz

# Allow original last shard to archive; otherwise recover any missing seed IDs.
for poll in $(seq 1 60); do
  status=$(gh api "repos/$GH_REPO/actions/runs/$MAIN_RUN" --jq '.status')
  count=$(gh api "repos/$GH_REPO/actions/runs/$MAIN_RUN/artifacts?per_page=100" --jq '.total_count')
  echo "SOURCE_RUN_POLL=$poll status=$status archived_artifacts=$count"
  if [ "$count" -ge 127 ] || [ "$status" = completed ]; then break; fi
  sleep 300
done

# Bulk download is efficient. Retry single archives on transient egress resets.
for attempt in 1 2 3; do
  if gh run download "$MAIN_RUN" --repo "$GH_REPO" \
       --pattern 'dack-aura-heldout-shard-*' --dir shards/official; then
    echo "BULK_DOWNLOAD_PASS attempt=$attempt"; break
  fi
  echo "BULK_DOWNLOAD_TRANSIENT_FAILURE attempt=$attempt"
  sleep 25
done
for shard in $(seq 0 127); do
  target="aura_heldout_shard_$shard.json.gz"
  if find shards -type f -name "$target" -print -quit | grep -q .; then
    continue
  fi
  echo "MISSING_ARCHIVED_SHARD=$shard; retrying named artifact"
  for attempt in 1 2 3 4; do
    mkdir -p "shards/repair_$shard"
    if gh run download "$MAIN_RUN" --repo "$GH_REPO" \
        --name "dack-aura-heldout-shard-$shard" --dir "shards/repair_$shard"; then
      break
    fi
    sleep 20
  done
  if find shards -type f -name "$target" -print -quit | grep -q .; then
    continue
  fi
  echo "REPLAY_ABSENT_SHARD_SEEDS=$shard"
  python -u dack_assertive_protected_auras_heldout_n1024_20261027.py \
    --shard "$shard" --games 8 \
    --out "shards/recovered/aura_heldout_shard_$shard.json.gz"
done

find shards -type f -name 'aura_heldout_shard_*.json.gz' | sort > archive_manifest.txt
echo "ARCHIVE_COUNT=$(wc -l < archive_manifest.txt)"
test "$(wc -l < archive_manifest.txt)" -eq 128
python -u dack_assertive_protected_auras_heldout_n1024_20261027.py \
  --pool --path shards \
  --out benchmark_results/dack_assertive_protected_auras_heldout_n1024_report.json
python - <<'PY'
import json
p="benchmark_results/dack_assertive_protected_auras_heldout_n1024_report.json"
r=json.load(open(p))
assert r["status"]=="PASS" and r["n"]==1024 and r["missing_count"]==0
assert r["shards_found"]==128 and len(r["arms"])==11
assert r["locked_auras"]==["Hardlight Containment","Lunarch Mantle"]
assert r["hashes"]["current"]=="a1c8e05dc3f9e1bcfbfbe2f7773ea4a5e62222d3440dd2f7417fd7f2f058c422"
print("ALL_1024_PAIRED_GAMES_AND_11_AURA_SAFE_VARIANTS_VALIDATED",flush=True)
for name in r["rank_by_T2_then_T3"]:
 a=r["arms"][name]
 ci=r["paired_vs_current"].get(name,{}).get("T2",{})
 print(name,a["T1_pct"],a["T2_pct"],a["T3_pct"],ci,flush=True)
PY
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add -f benchmark_results/dack_assertive_protected_auras_heldout_n1024_report.json \
  benchmark_results/dack_assertive_protected_auras_heldout_n1024_report.raw.json.gz
git commit -m 'Recover shard104 artifact and publish full independent N1024 protected-aura heldout'
git push
