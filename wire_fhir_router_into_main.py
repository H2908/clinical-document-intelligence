"""Register the FHIR router in api/main.py.

Two anchored replacements:
  1. Add 'fhir' to the routes import tuple (alongside jobs).
  2. Add app.include_router(fhir.router, ...) to the registration block.

Idempotent.
"""
from pathlib import Path

p = Path("api/main.py")
src = p.read_text(encoding="utf-8")

if "fhir.router" in src:
    print("[SKIP] fhir router already wired")
    raise SystemExit(0)

# 1. Add 'fhir' to imports
old_import = '''from api.routes import (
    patients,
    documents,
    notes,
    labs,
    flags,
    contradictions,
    briefing,
    timeline,
    jobs,
)'''
new_import = '''from api.routes import (
    patients,
    documents,
    notes,
    labs,
    flags,
    contradictions,
    briefing,
    timeline,
    jobs,
    fhir,
)'''
if old_import not in src:
    print("[FAIL] import-tuple anchor not found")
    raise SystemExit(1)
src = src.replace(old_import, new_import)

# 2. Register router after jobs
old_reg = 'app.include_router(jobs.router,     prefix="/api", tags=["jobs"])'
new_reg = ('app.include_router(jobs.router,     prefix="/api", tags=["jobs"])\n'
           'app.include_router(fhir.router,     prefix="/api", tags=["fhir"])')
if old_reg not in src:
    print("[FAIL] jobs.router include anchor not found")
    raise SystemExit(1)
src = src.replace(old_reg, new_reg)

p.write_text(src, encoding="utf-8", newline="\n")
print("OK fhir router wired into main.py")