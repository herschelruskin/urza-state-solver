from pathlib import Path
import subprocess

BASELINE = "26e15d2355400efe12cb457d5bb0dc63bce8cc3b"

parallel = Path("rust/crates/urza-mc/src/parallel.rs")
text = parallel.read_text()
old_import = (
    "    ADAPTIVE_ROOT_EVAL_VERSION, AdaptiveRootActionComparison, AdaptiveRootConfig, "
    "AdaptiveRootError,\n"
)
new_import = "    AdaptiveRootActionComparison, AdaptiveRootConfig, AdaptiveRootError,\n"
if old_import in text:
    text = text.replace(old_import, new_import, 1)
elif "ADAPTIVE_ROOT_EVAL_VERSION" in text:
    raise SystemExit("parallel unused-import repair anchor changed unexpectedly")
parallel.write_text(text)

baseline = subprocess.check_output(
    ["git", "show", f"{BASELINE}:rust/crates/urza-mc/src/lib.rs"],
    text=True,
)
marker = "mod adaptive;\npub use adaptive::*;\nmod root;"
replacement = "mod adaptive;\npub use adaptive::*;\nmod parallel;\npub use parallel::*;\nmod root;"
if marker not in baseline:
    raise SystemExit("accepted urza-mc module-export anchor missing")
Path("rust/crates/urza-mc/src/lib.rs").write_text(baseline.replace(marker, replacement, 1))
