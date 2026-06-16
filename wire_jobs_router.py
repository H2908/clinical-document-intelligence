"""Wire api/routes/jobs.py into api/main.py.

Two anchored replacements:
  1. Add 'jobs' to the routes import tuple
  2. Add app.include_router(jobs.router, ...) to the registration block

Atomic: aborts if either anchor is missing or already present.
"""
from pathlib import Path

p = Path("api/main.py")
src = p.read_text(encoding="utf-8")

if "from api.routes import" not in src:
    print("[FAIL] route-import block not found")
    raise SystemExit(1)
if "jobs,\n" in src and "jobs.router" in src:
    print("[SKIP] jobs router already wired")
    raise SystemExit(0)

# 1. Add 'jobs' to import tuple
old_import = '''from api.routes import (
    patients,
    documents,
    notes,
    labs,
    flags,
    contradictions,
    briefing,
    timeline,
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
)'''

if old_import not in src:
    print("[FAIL] import-tuple anchor not found")
    raise SystemExit(1)
src = src.replace(old_import, new_import)

# 2. Add include_router after timeline registration
old_reg = 'app.include_router(timeline.router, prefix="/api", tags=["timeline"])'
new_reg = ('app.include_router(timeline.router, prefix="/api", tags=["timeline"])\n'
           'app.include_router(jobs.router,     prefix="/api", tags=["jobs"])')

if old_reg not in src:
    print("[FAIL] router-registration anchor not found")
    raise SystemExit(1)
src = src.replace(old_reg, new_reg)

p.write_text(src, encoding="utf-8", newline="\n")
print("OK jobs router wired")