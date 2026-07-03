"""Fix run_mtsamples_hybrid_full_capture.py to register the VerdictCapture
handler on the module logger ONLY, and disable propagation to root for
the duration of capture, so each VERDICT line is captured exactly once.

Root cause: the original script added the handler to both
"agents.flag_agent" and the root logger. Python's logging propagates
records upward by default, so every log.warning() call in flag_agent
triggered emit() twice - once at the module logger, once again at root.
This produced literal duplicate dict entries in rejected_candidates,
which would silently double-count in any aggregate stats.
"""
from pathlib import Path

p = Path("run_mtsamples_hybrid_full_capture.py")
src = p.read_text(encoding="utf-8")

old = '''capture = VerdictCapture()
capture.setLevel(logging.WARNING)
logging.getLogger("agents.flag_agent").addHandler(capture)
logging.getLogger().addHandler(capture)  # root, in case logger name differs'''

new = '''capture = VerdictCapture()
capture.setLevel(logging.WARNING)
_flag_logger = logging.getLogger("agents.flag_agent")
_flag_logger.addHandler(capture)
# Disable propagation to root while capturing, so each VERDICT line is
# captured exactly once. Fixed after discovering the original dual
# registration (module logger + root logger) caused every VERDICT to be
# captured twice - a real JSONL duplicate, not just a display artifact,
# confirmed by inspecting rejected_candidates array length directly.
_flag_logger.propagate = False'''

if old not in src:
    print("[FAIL] anchor not found")
    raise SystemExit(1)
src = src.replace(old, new, 1)
print("[OK] handler registration fixed: module logger only, propagation disabled")

p.write_text(src, encoding="utf-8", newline="\n")

import ast
try:
    ast.parse(src)
    print("[OK] AST valid")
except SyntaxError as e:
    print(f"[FAIL] {e}")
    raise SystemExit(1)
