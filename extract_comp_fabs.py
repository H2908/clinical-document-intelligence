"""Pull every composition-fabrication rejection from day2_5x_v13.log along with
the document text so each can be eyeballed."""
import re

with open("day2_5x_v13.log", encoding="utf-8", errors="replace") as f:
    text = f.read()

# Split into per-run sections
runs = re.split(r"===== RUN (\d+) =====", text)
# runs[0] is empty pre-amble; then alternating [run_id, run_body, run_id, run_body...]

# We want every composition-fabrication block. Each block is a 
# "WARNING ===== ... VERDICT: composition-fabrication ... =====" envelope.
# Extract the LLM quote and LLM description lines that precede each.

pattern = re.compile(
    r"WARNING ={70}\s*\n"
    r"WARNING HYBRID VALIDATOR REJECTION on doc (?P<doc>\S+)\s*\n"
    r"WARNING LLM quote: '(?P<quote>[^\n]+)'\s*\n"
    r"WARNING LLM description: '(?P<desc>[^\n]+)'\s*\n"
    r"WARNING (?P<verdict_line>VERDICT: composition-fabrication[^\n]+)",
    re.MULTILINE,
)

matches = list(pattern.finditer(text))
print(f"Found {len(matches)} composition-fabrication rejections in 5x log")
print()

for i, m in enumerate(matches, 1):
    print(f"--- Composition-fabrication #{i} ---")
    print(f"  cited_doc:   {m.group('doc')}")
    print(f"  description: {m.group('desc')}")
    print(f"  quote:       {m.group('quote')}")
    print(f"  {m.group('verdict_line')}")
    print()