"""V2: complete remaining edits using regex instead of literal anchor.

V1 succeeded on edits 1-2 (useRouter import, form signature) but failed
on edit 3 (createPatient call) - likely CRLF vs LF line-ending mismatch
between the file and my literal anchor.

This v2 uses regex with multiline mode, which tolerates either line
ending. Three remaining edits.
"""
from pathlib import Path
import re

p = Path("frontend/app/page.tsx")
src = p.read_text(encoding="utf-8")

# Edit 3: capture createPatient result
# Pattern matches `await api.createPatient(form);` followed by `onCreated();`
# with any whitespace in between
pat_create = re.compile(
    r'(\s+)await api\.createPatient\(form\);\s*\n\s+onCreated\(\);',
    re.MULTILINE,
)

if "const card = await api.createPatient(form);" in src:
    print("[SKIP] createPatient call already updated")
else:
    m = pat_create.search(src)
    if m is None:
        print("[FAIL] createPatient call pattern still not matching - paste the bytes")
        raise SystemExit(1)
    indent = m.group(1)
    new_block = f"{indent}const card = await api.createPatient(form);{indent}onCreated(card);"
    src = src[:m.start()] + new_block + src[m.end():]
    print(f"[OK] createPatient call captures result, passes card to onCreated")

# Edit 4: add `const router = useRouter();` inside LandingPage
old_anchor = "const [showForm, setShowForm] = useState(false);"
new_block = "const [showForm, setShowForm] = useState(false);\n  const router = useRouter();"

if "const router = useRouter();" in src:
    print("[SKIP] router already initialised")
else:
    if old_anchor not in src:
        print("[FAIL] LandingPage state anchor not found")
        raise SystemExit(1)
    src = src.replace(old_anchor, new_block, 1)
    print("[OK] router initialised in LandingPage")

# Edit 5: update onCreated handler in the JSX
pat_handler = re.compile(
    r'<NewPatientForm onCreated=\{\(\) => \{ setShowForm\(false\); load\(\); \}\} />',
)

if "router.push(`/patients/${card.id}`)" in src:
    print("[SKIP] onCreated handler already updated")
else:
    if pat_handler.search(src) is None:
        # Try a more flexible pattern - any handler that calls setShowForm(false) and load()
        pat_handler2 = re.compile(
            r'<NewPatientForm\s+onCreated=\{[^}]*setShowForm\(false\)[^}]*load\(\)[^}]*\}\s*/>',
        )
        if pat_handler2.search(src) is None:
            print("[FAIL] onCreated handler not matching - paste the bytes")
            raise SystemExit(1)
        src = pat_handler2.sub(
            '<NewPatientForm onCreated={(card) => { setShowForm(false); router.push(`/patients/${card.id}`); }} />',
            src,
        )
    else:
        src = pat_handler.sub(
            '<NewPatientForm onCreated={(card) => { setShowForm(false); router.push(`/patients/${card.id}`); }} />',
            src,
        )
    print("[OK] onCreated handler now navigates to new patient's page")

p.write_text(src, encoding="utf-8", newline="\n")
print()
print("All five edits complete. Test in browser:")
print("  - Hot-reload should pick up changes automatically")
print("  - Click + Add patient, fill form, Create")
print("  - Expect: form closes, URL changes to /patients/pat_XXXXXXXX")