# Standalone Pipeline — Full Extraction and Grounding-Validation Engine

This directory contains a standalone, credential-gated implementation
of the full extraction and LLM-grounding-validation pipeline described
in the paper. It is provided for reviewer verification: unlike the
public demo (which serves pre-computed fixtures and requires no
credentials), running this pipeline performs live inference against
the Anthropic API using your own API key.

## What this is, precisely

- `extraction.py` — PDF parsing (PyMuPDF) → text cleaning → NER
  (scispaCy + dictionary/regex augmentation) → negation detection.
  Faithfully extracted from the production pipeline; verified to
  produce an identical entity count (45/45) against the production
  pipeline on a real test document.
- `grounding.py` — the four-guard grounding validator described in the
  paper, including Guard 3 (contiguous-grounding check), this paper's
  principal technical contribution. Pure functions, no LLM calls, no
  I/O — independently testable. 15/15 unit tests pass, covering the
  paper's flagship composition-fabrication example and the calibration
  fix described in the Evaluation section.
- `llm_client.py` — a thin wrapper around the Claude API, fixed to the
  exact sampling parameters used throughout the paper (model
  `claude-sonnet-4-6`, temperature 0.7, max_tokens 1500).
- `run_pipeline.py` — ties the above together: PDF in, JSON out.

## What this is NOT

This standalone pipeline is a narrower slice than the full production
system, by deliberate scope decision, stated here rather than hidden:

- **No lab-observation parsing.** The production worker extracts
  structured lab values (via `nlp/lab_parser.py`); this standalone
  script does not. Lab values are not central to this paper's claims
  (safety flags, grounding validation, contradiction detection).
- **No full relative-date normalisation.** The production worker
  resolves relative dates ("6 weeks ago") against document context;
  this script extracts date-shaped text spans but does not resolve them.
- **No contradiction detection.** The paper's contradiction-detection
  agent (cross-document claim comparison) is a separate module in the
  private research codebase and is not included in this standalone
  script. `run_pipeline.py` operates on a single document at a time.
- **No OCR fallback.** Scanned/image-based PDFs with no extractable
  text layer will raise a clear error rather than silently failing or
  attempting OCR (the production worker has an OCR fallback; this
  script does not).
- **Verified against a specific, bounded set of documents**, not
  arbitrary PDFs: the two synthetic patients and ten MTSamples
  documents used in the paper's evaluation (see paper, Evaluation
  section). We have not tested this script against documents outside
  that set, and make no robustness claim beyond it.

## Setup

```bash
cd pipeline
pip install -r requirements.txt
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz
```

Create a `.env` file in this directory (never committed — see
`.gitignore`) containing:

```
ANTHROPIC_API_KEY=your-own-key-here
```

Your API key is read once from the environment at call time and is
never logged, transmitted anywhere other than the official Anthropic
API endpoint, or stored by this code.

## Running

```bash
python run_pipeline.py --input path/to/document.pdf --output results/output.json --verbose
```

## Testing

```bash
pytest tests/ -v
```

`tests/test_grounding.py` (15 tests) requires no model and no API key —
it tests the pure grounding-validation logic directly, including the
paper's flagship composition-fabrication example.

`tests/test_extraction.py` (24 tests) runs 22 tests with no model
required; 2 additional tests requiring the scispaCy model are skipped
automatically if it is not installed.

## A note on reproducibility and sampling variance

Because the LLM-assisted stage samples at temperature 0.7, running
this script twice on the same document will not necessarily produce
identical flag proposals — this is expected, documented, and is
exactly the phenomenon the paper's reproducibility measurement
(Section: Evaluation) quantifies. What should be reproducible run to
run is the grounding-validation *behaviour*: a genuinely verbatim,
contiguous quote should be accepted, and a fabricated or
non-contiguous quote should be rejected, regardless of which specific
flags the model happens to propose on a given run.
