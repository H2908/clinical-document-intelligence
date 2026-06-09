"""
Verification test for CONTRADICTION_VALIDATE_PROVENANCE switch.

Forces the LLM to return two known contradictions:
  - one valid (cites real doc_ids)
  - one phantom (cites doc_DOESNOTEXIST)

Asserts the switch flips n_returned from 1 → 2 between validate=True and
validate=False, while n_would_be_rejected stays at 1 in both cases.

This proves the switch is doing its job, not just compiling.
"""
import json
from unittest.mock import patch, MagicMock

from agents.contradiction_agent import _llm_find_contradictions


# ---------------------------------------------------------------------------
# Fake LLM output — two contradictions, one valid, one phantom
# ---------------------------------------------------------------------------
FAKE_LLM_PAYLOAD = [
    {
        "severity": "HIGH",
        "category": "ALLERGY_CONFLICT",
        "doc_a_id": "doc_real_001",
        "doc_a_statement": "NKDA documented",
        "doc_b_id": "doc_real_002",
        "doc_b_statement": "Penicillin allergy noted",
        "explanation": "Documents disagree on allergy history",
    },
    {
        "severity": "MEDIUM",
        "category": "MEDICATION_CONFLICT",
        "doc_a_id": "doc_real_001",
        "doc_a_statement": "On atorvastatin 40mg",
        "doc_b_id": "doc_DOESNOTEXIST",         # ← phantom citation
        "doc_b_statement": "Atorvastatin stopped",
        "explanation": "Documents disagree on current statin",
    },
]

# Real document set — only doc_real_001 and doc_real_002 exist
DOCUMENTS = [
    {"document_id": "doc_real_001", "doc_type": "clinic_letter", "document_date": "2024-01-01"},
    {"document_id": "doc_real_002", "doc_type": "discharge_summary", "document_date": "2024-02-01"},
]

# Doc summaries (minimal — prompt builder will use this)
DOC_SUMMARIES = [
    {"document_id": "doc_real_001", "doc_type": "clinic_letter",
     "document_date": "2024-01-01", "entities": []},
    {"document_id": "doc_real_002", "doc_type": "discharge_summary",
     "document_date": "2024-02-01", "entities": []},
]


def make_fake_anthropic_response():
    """Build a fake response object shaped like Anthropic SDK's return."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(FAKE_LLM_PAYLOAD))]
    return mock_response


def run_one(validate: bool) -> dict:
    """Run _llm_find_contradictions with the LLM mocked. Returns metadata."""
    with patch("agents.contradiction_agent.Anthropic") as MockAnthropic:
        # MockAnthropic() returns a mock client whose .messages.create returns our fake response
        mock_client = MagicMock()
        mock_client.messages.create.return_value = make_fake_anthropic_response()
        MockAnthropic.return_value = mock_client

        items, metadata = _llm_find_contradictions(
            DOC_SUMMARIES, DOCUMENTS, validate=validate,
        )

    return {"items": items, "metadata": metadata}


def main():
    print("=" * 70)
    print("VERIFICATION: CONTRADICTION_VALIDATE_PROVENANCE switch")
    print("=" * 70)
    print()
    print("Setup:")
    print(f"  Fake LLM returns 2 contradictions:")
    print(f"    [0] cites real doc_ids (doc_real_001, doc_real_002)  — VALID")
    print(f"    [1] cites phantom doc_id (doc_DOESNOTEXIST)          — INVALID")
    print(f"  Real document set: doc_real_001, doc_real_002")
    print()

    # validate=True
    print("--- Run A: validate=True (production default) ---")
    a = run_one(validate=True)
    print(f"  n_returned          = {len(a['items'])}")
    print(f"  n_parsed            = {a['metadata']['n_parsed']}")
    print(f"  n_rejected          = {a['metadata']['n_rejected']}")
    print(f"  rejection_reasons   = {a['metadata']['rejection_reasons']}")
    print()

    # validate=False
    print("--- Run B: validate=False (paper ablation) ---")
    b = run_one(validate=False)
    print(f"  n_returned          = {len(b['items'])}")
    print(f"  n_parsed            = {b['metadata']['n_parsed']}")
    print(f"  n_rejected          = {b['metadata']['n_rejected']}")
    print(f"  rejection_reasons   = {b['metadata']['rejection_reasons']}")
    print()

    # The advisor's specified assertions
    print("=" * 70)
    print("ADVISOR'S REQUIRED ASSERTIONS")
    print("=" * 70)

    checks = [
        ("validate=True returns 1 item",        len(a['items']) == 1),
        ("validate=True rejected_count is 1",   a['metadata']['n_rejected'] == 1),
        ("validate=False returns 2 items",      len(b['items']) == 2),
        ("validate=False rejected_count is 1",  b['metadata']['n_rejected'] == 1),
        ("n_parsed is 2 in both",
         a['metadata']['n_parsed'] == 2 and b['metadata']['n_parsed'] == 2),
        ("Switch flips n_returned: 1 → 2",
         len(a['items']) == 1 and len(b['items']) == 2),
        ("n_rejected is invariant across switch states",
         a['metadata']['n_rejected'] == b['metadata']['n_rejected']),
    ]

    all_passed = True
    for desc, passed in checks:
        mark = "✓" if passed else "✗"
        if not passed:
            all_passed = False
        print(f"  {mark}  {desc}")

    print()
    print("=" * 70)
    if all_passed:
        print("RESULT: ALL CHECKS PASSED — switch is verified.")
    else:
        print("RESULT: ONE OR MORE CHECKS FAILED — switch is NOT verified.")
    print("=" * 70)


if __name__ == "__main__":
    main()