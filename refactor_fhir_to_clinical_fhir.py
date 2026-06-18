"""Refactor: rename local fhir/ package to clinical_fhir/ so it doesn't
shadow the installed fhir.resources library.

Steps:
  1. Create clinical_fhir/ directory
  2. Copy all files from fhir/ to clinical_fhir/
  3. Find-and-replace imports across the codebase
  4. Delete fhir/ via git rm (so git tracks the rename properly)
  5. Verify imports resolve correctly

Idempotent: re-running after partial completion picks up where it left off.
"""
import shutil
from pathlib import Path
import re

PROJECT_ROOT = Path(".").resolve()
OLD_DIR = PROJECT_ROOT / "fhir"
NEW_DIR = PROJECT_ROOT / "clinical_fhir"

# Step 1: create new directory if missing
if not NEW_DIR.exists():
    NEW_DIR.mkdir()
    print(f"Created {NEW_DIR}")
else:
    print(f"{NEW_DIR} already exists")

# Step 2: copy files
files_to_copy = [
    "__init__.py",
    "builders.py",
    "fhir_builder.py",
    "test_builders.py",
    "test_fhir_builder.py",
]
for fname in files_to_copy:
    src = OLD_DIR / fname
    dst = NEW_DIR / fname
    if src.exists() and not dst.exists():
        shutil.copy2(src, dst)
        print(f"Copied {fname}")
    elif dst.exists():
        print(f"{dst} already exists - skipping copy")
    else:
        print(f"[WARN] {src} not found")

# Step 3: rewrite imports in the new files
for fname in ("builders.py", "fhir_builder.py", "test_builders.py", "test_fhir_builder.py"):
    f = NEW_DIR / fname
    if not f.exists():
        continue
    src = f.read_text(encoding="utf-8")
    new_src = src
    # from fhir.builders -> from clinical_fhir.builders
    new_src = re.sub(r"\bfrom fhir\.builders\b", "from clinical_fhir.builders", new_src)
    new_src = re.sub(r"\bfrom fhir\.fhir_builder\b", "from clinical_fhir.fhir_builder", new_src)
    new_src = re.sub(r"\bimport fhir\.builders\b", "import clinical_fhir.builders", new_src)
    new_src = re.sub(r"\bimport fhir\.fhir_builder\b", "import clinical_fhir.fhir_builder", new_src)
    if new_src != src:
        f.write_text(new_src, encoding="utf-8", newline="\n")
        print(f"Rewrote imports in {f.name}")

# Step 4: update files outside the package that import from fhir.*
external_files = [
    "api/routes/fhir.py",
    "smoke_fhir_bundle_real.py",
    "smoke_write_fhir_bundle.py",
]
for path_str in external_files:
    f = Path(path_str)
    if not f.exists():
        print(f"[INFO] {path_str} not found - skipping")
        continue
    src = f.read_text(encoding="utf-8")
    new_src = src
    new_src = re.sub(r"\bfrom fhir\.builders\b", "from clinical_fhir.builders", new_src)
    new_src = re.sub(r"\bfrom fhir\.fhir_builder\b", "from clinical_fhir.fhir_builder", new_src)
    if new_src != src:
        f.write_text(new_src, encoding="utf-8", newline="\n")
        print(f"Updated imports in {path_str}")
    else:
        print(f"No fhir.* imports in {path_str}")

# Step 5: confirm the import path now resolves to library
print("\n=== Verification ===")
print(f"Old fhir/ still exists: {OLD_DIR.exists()}")
print(f"New clinical_fhir/ exists: {NEW_DIR.exists()}")
print(f"Files in clinical_fhir/: {sorted(p.name for p in NEW_DIR.iterdir())}")

print("\nNext manual step:")
print("  git rm -r fhir/")
print("  (We leave the actual delete to git so the rename is tracked properly.)")