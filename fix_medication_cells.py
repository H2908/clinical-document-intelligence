"""Fix medication table cells: bind to m.last_prescribed (not m.started)
and remove the Flag <td> entirely.

Header already updated; only the row cells remain. Anchored on exact
visible bytes from the file.
"""
from pathlib import Path

p = Path("frontend/app/patients/[id]/page.tsx")
src = p.read_text(encoding="utf-8")

old_cells = '''                      <td className="px-5 py-3 text-slate-500 text-xs font-mono">{m.started || "—"}</td>
                      <td className="px-5 py-3">
                        {m.flag ? (
                          <span className="inline-flex items-center gap-1 text-xs text-amber-700">
                            <WarnIcon />
                            {m.flag}
                          </span>
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>'''

new_cells = '''                      <td className="px-5 py-3 text-slate-500 text-xs font-mono">{m.last_prescribed || "—"}</td>'''

if "m.last_prescribed" in src and "m.flag" not in src:
    print("[SKIP] cells already updated")
elif old_cells not in src:
    print("[FAIL] cells anchor not matching - check em-dash encoding")
    raise SystemExit(1)
else:
    src = src.replace(old_cells, new_cells)
    p.write_text(src, encoding="utf-8", newline="\n")
    print("[OK] medication cells: m.started -> m.last_prescribed, Flag <td> removed")