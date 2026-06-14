"""Phase 1 / Task 2 — cache-bug check.

Call detect_flags() twice in a row with identical inputs (same patient,
same entities, same docs) and compare outputs. If the two calls return
byte-identical LLM-emitted flags, there's caching somewhere and the
held-out reproducibility metric is invalid (cached calls don't represent
real LLM variance).

We run hybrid_validated mode because it exercises both the rule layer
(should match exactly) AND the LLM second-pass (which is the actual
source of variance we care about).
"""
import os
import json
from dotenv import load_dotenv
load_dotenv()

# Force hybrid_validated mode for the LLM second-pass
os.environ["FLAG_AGENT_MODE"] = "llm_naive"

from database.snowflake_reader import (
    read_entities_for_patient,
    read_documents_for_patient,
)
from agents.flag_agent import detect_flags

PATIENT = "pat_test_01"

print(f"Cache-bug check: calling detect_flags() twice on {PATIENT}")
print(f"Mode: llm_naive (pure LLM, no validator)")
print()

entities = read_entities_for_patient(PATIENT)
documents = read_documents_for_patient(PATIENT)
print(f"Loaded {len(entities)} entities, {len(documents)} documents")
print()

print("Call 1...")
flags_1, meta_1 = detect_flags(PATIENT, entities, documents)
print(f"  -> {len(flags_1)} flags, {len(meta_1.get('errors', []))} errors")

print("Call 2...")
flags_2, meta_2 = detect_flags(PATIENT, entities, documents)
print(f"  -> {len(flags_2)} flags, {len(meta_2.get('errors', []))} errors")
print()

# Compare the LLM-emitted flags (those with cited_document_id, not source_document_id)
llm_1 = [f for f in flags_1 if "cited_document_id" in f]
llm_2 = [f for f in flags_2 if "cited_document_id" in f]

print(f"LLM flags in call 1: {len(llm_1)}")
print(f"LLM flags in call 2: {len(llm_2)}")
print()

# Are the descriptions byte-identical between the two calls?
# If yes → caching. If no → independent LLM calls.
desc_1 = sorted(f.get("description", "") for f in llm_1)
desc_2 = sorted(f.get("description", "") for f in llm_2)

if desc_1 == desc_2 and len(desc_1) > 0:
    print("[POSSIBLE CACHE BUG] Both calls returned IDENTICAL LLM descriptions.")
    print("This could mean:")
    print("  (a) LLM happened to produce identical output (possible at temp=0.7 but rare)")
    print("  (b) A cache is intercepting calls — would invalidate paper reproducibility")
    print()
    print("Descriptions (same in both calls):")
    for d in desc_1:
        print(f"  {d!r}")
elif len(desc_1) == 0 and len(desc_2) == 0:
    print("[INCONCLUSIVE] Both calls returned 0 LLM flags. Cannot detect cache.")
else:
    print("[OK] Outputs DIFFER between calls — no caching detected.")
    print()
    print(f"Unique to call 1 ({len(set(desc_1) - set(desc_2))} descriptions):")
    for d in sorted(set(desc_1) - set(desc_2)):
        print(f"  {d!r}")
    print()
    print(f"Unique to call 2 ({len(set(desc_2) - set(desc_1))} descriptions):")
    for d in sorted(set(desc_2) - set(desc_1)):
        print(f"  {d!r}")
    print()
    print(f"Shared between both ({len(set(desc_1) & set(desc_2))} descriptions):")
    for d in sorted(set(desc_1) & set(desc_2)):
        print(f"  {d!r}")