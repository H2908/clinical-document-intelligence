"""Frontend fix: navigate to the new patient's page after Add Patient.

Currently: form submits, createPatient succeeds, onCreated() closes the
form and re-runs load() to refresh the list. The new patient IS in the
database, but the UI gives no clear feedback because the user is left
on the home page expecting to "see" the patient somehow.

Fix: after successful create, navigate to the new patient's overview
page. That's the natural workflow - you just made a patient, now you
want to add documents to them.

Two anchored edits in app/page.tsx:
  1. NewPatientForm: capture the result of createPatient and pass the
     new PatientCard back via onCreated(card).
  2. LandingPage: change onCreated handler to push to /patients/{id}.

Also adds the useRouter import from next/navigation if not present.
"""
from pathlib import Path

p = Path("frontend/app/page.tsx")
src = p.read_text(encoding="utf-8")

# 1. Ensure useRouter is imported from next/navigation
if "useRouter" not in src:
    # Find the existing next/navigation import or add one
    if 'from "next/navigation"' in src:
        # Existing import - extend it
        old = src.split('from "next/navigation"')[0].rsplit("import", 1)
        if len(old) == 2:
            print("[INFO] next/navigation import found; adding useRouter to it")
            # Surgical: replace 'import { X } from "next/navigation"' with
            # 'import { X, useRouter } from "next/navigation"'
            import re
            src = re.sub(
                r'import \{([^}]+)\} from "next/navigation"',
                lambda m: f'import {{{m.group(1).rstrip()}, useRouter}} from "next/navigation"',
                src,
                count=1,
            )
    else:
        # No next/navigation import - add it after the React import
        old_react = 'from "react";'
        new_react = 'from "react";\nimport { useRouter } from "next/navigation";'
        if old_react in src:
            src = src.replace(old_react, new_react, 1)
            print("[OK] useRouter import added after React import")
        else:
            print("[FAIL] could not find React import anchor to add useRouter")
            raise SystemExit(1)
else:
    print("[SKIP] useRouter already imported")

# 2. NewPatientForm: change onCreated signature and pass the result
old_form_signature = 'function NewPatientForm({ onCreated }: { onCreated: () => void }) {'
new_form_signature = 'function NewPatientForm({ onCreated }: { onCreated: (card: PatientCard) => void }) {'
if old_form_signature in src:
    src = src.replace(old_form_signature, new_form_signature)
    print("[OK] NewPatientForm onCreated signature accepts PatientCard")
elif new_form_signature in src:
    print("[SKIP] NewPatientForm signature already updated")
else:
    print("[FAIL] NewPatientForm signature anchor not found")
    raise SystemExit(1)

# 3. NewPatientForm: capture createPatient result and pass it back
old_create_call = '''        await api.createPatient(form);
        onCreated();'''
new_create_call = '''        const card = await api.createPatient(form);
        onCreated(card);'''
if old_create_call in src:
    src = src.replace(old_create_call, new_create_call)
    print("[OK] NewPatientForm now passes new card to onCreated")
elif new_create_call in src:
    print("[SKIP] NewPatientForm createPatient call already updated")
else:
    print("[FAIL] createPatient call anchor not found")
    raise SystemExit(1)

# 4. LandingPage: use the new card to navigate
# First need to add `const router = useRouter();` inside LandingPage
old_landing_state_anchor = 'const [showForm, setShowForm] = useState(false);'
new_landing_state_block = '''const [showForm, setShowForm] = useState(false);
  const router = useRouter();'''
if "const router = useRouter();" in src:
    print("[SKIP] router already initialised")
else:
    if old_landing_state_anchor not in src:
        print("[FAIL] LandingPage state anchor not found")
        raise SystemExit(1)
    src = src.replace(old_landing_state_anchor, new_landing_state_block, 1)
    print("[OK] router initialised in LandingPage")

# 5. Update onCreated handler to navigate
old_handler = '<NewPatientForm onCreated={() => { setShowForm(false); load(); }} />'
new_handler = '<NewPatientForm onCreated={(card) => { setShowForm(false); router.push(`/patients/${card.id}`); }} />'
if old_handler in src:
    src = src.replace(old_handler, new_handler)
    print("[OK] onCreated handler now navigates to new patient's page")
elif new_handler in src:
    print("[SKIP] onCreated handler already updated")
else:
    print("[FAIL] onCreated handler anchor not found")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8", newline="\n")
print()
print("=== Summary ===")
print("Add Patient flow now:")
print("  1. Form submits, calls api.createPatient")
print("  2. Backend returns PatientCard with id")
print("  3. Form closes, router pushes to /patients/{new_id}")
print("  4. User lands on the new patient's overview page")
print()
print("Test in browser:")
print("  1. Restart frontend if hot-reload doesn't pick up (Ctrl+C, npm run dev)")
print("  2. Click + Add patient")
print("  3. Fill in name/DOB/NHS/sex")
print("  4. Click Create")
print("  5. Expect: navigate to /patients/pat_XXXXXXXX overview page")