"""Replace the complex lambda dose parser with a clean helper function."""
from pathlib import Path
import re, ast

p = Path("demo/api/main.py")
src = p.read_text(encoding="utf-8")

# Add a simple helper function after the imports
helper = '''
def _parse_dose(drug_text: str) -> str:
    """Extract dose from drug name text e.g. 'Ramipril 5 mg OD' -> '5 mg'."""
    m = re.search(r"\\d+[\\d.]*\\s*(?:mg|mcg|g|ml|units?|iu)", drug_text, re.IGNORECASE)
    return m.group(0) if m else ""


def _is_noise_med(drug_text: str) -> bool:
    """Filter out NER artefacts like 'furosemide dose', 'insulin therapy'."""
    noise = {"dose", "therapy", "treatment", "use", "review", "clinic", "started"}
    tokens = drug_text.strip().lower().split()
    return bool(tokens and tokens[-1] in noise) or len(tokens) > 5

'''

# Insert helper after the JOBS dict definition
anchor = "# ── In-memory job store (demo only)"
if anchor not in src:
    print("[FAIL] insertion anchor not found")
    raise SystemExit(1)
src = src.replace(anchor, helper + anchor, 1)
print("[OK] helper functions added")

# Now replace the complex lambda dose expressions with _parse_dose()
src = re.sub(
    r'\(lambda t: \(re\.search\(.*?\)\(\)\)\.group\(0\)\)\(m\.get\("drug",""\)\)',
    '_parse_dose(m.get("drug", ""))',
    src,
    flags=re.DOTALL
)
print("[OK] lambda expressions replaced with _parse_dose()")

# Replace noise filter
src = src.replace(
    'and m.get("drug","").strip().lower().split()[-1] not in {"dose","therapy","treatment","use","review","clinic"}\n            and len(m.get("drug","").strip().split()) < 6',
    'and not _is_noise_med(m.get("drug", ""))'
)
print("[OK] noise filter simplified")

try:
    ast.parse(src)
    print("[OK] AST valid")
except SyntaxError as e:
    print(f"[FAIL] SyntaxError: {e}")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")
print("[OK] demo/api/main.py saved - uvicorn --reload will pick this up")