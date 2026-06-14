from pathlib import Path

addition = '''

/* ---- Print: hide app chrome, show only briefing ---- */
@media print {
  aside { display: none !important; }
  body, html { background: white !important; }
  .print-hide { display: none !important; }
  main { padding: 0 !important; }
  .max-w-5xl { max-width: none !important; }
  section { break-inside: avoid; }
  * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
}
'''

target = Path("frontend/app/globals.css")
existing = target.read_text(encoding="utf-8")
if "@media print" in existing:
    print("Print rules already present in globals.css; not appending again.")
else:
    target.write_text(existing + addition, encoding="utf-8", newline="\n")
    print(f"Appended print rules to {target}")
print(f"Total lines now: {len(target.read_text(encoding='utf-8').splitlines())}")