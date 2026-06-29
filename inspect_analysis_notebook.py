"""Quick inspection of evaluation/analysis.ipynb to see what's in it."""
import json
from pathlib import Path

nb_path = Path("evaluation/analysis.ipynb")
nb = json.loads(nb_path.read_text(encoding="utf-8"))

print(f"File:  {nb_path}")
print(f"Cells: {len(nb['cells'])}")
print()
for i, c in enumerate(nb["cells"]):
    src = "".join(c["source"])
    first_line = src.split("\n")[0][:90]
    print(f"  [{i:>2}] {c['cell_type']:9} | {first_line}")