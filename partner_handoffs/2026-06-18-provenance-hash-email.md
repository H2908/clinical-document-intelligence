\*\*Subject:\*\* Schema migration request — CORE.flag.provenance\_hash for tamper-evidence



Hi \[Partner name],



Quick schema migration on the Snowflake side, low cost (<1s of DDL, no data backfill). Background, then the ask:



\*\*Background.\*\* As part of the AAAI 2027 submission methodology we're adding tamper-evident provenance hashing to every emitted flag. The hash is a SHA-256 digest of the flag's provenance fields (source\_quote, cited\_document\_id, source\_document\_id) + content fields (severity, category, clinical\_subject, description) + generation context (model, prompt\_version, temperature). It proves the flag was emitted exactly as recorded; downstream edits to any of those fields are detectable via hash mismatch.



The hash function and verifier are landed and tested on our side:

\- `agents/audit\_agent.py` — `hash\_flag()`, `verify\_jsonl\_run()`, CLI

\- 7-case test set passing 7/7 including the three load-bearing tampering-detection cases (description tampered, source\_quote tampered, context tampered all detected)

\- Verifier runs cleanly against pre-instrumentation JSONL data (141 flags reported as `no\_stored\_hash` rather than `mismatch` — correct behaviour for unverifiable historical data)



\*\*The ask.\*\* Add a nullable `provenance\_hash VARCHAR(64)` column to `CORE.flag` and update `SP\_WRITE\_FLAGS` to copy it from the incoming JSON. Migration script is attached as `2026-06-18-provenance-hash-migration.sql`. If you'd like to coordinate on the exact proc diff, happy to send the current proc body in advance.



Existing rows stay NULL (no backfill needed — those are pre-instrumentation and the audit agent handles that case explicitly). Once the column lands, the next smoke run from our side will write flags with hashes populated, and the next paper-quality assertion in the submission can cite "every flag emitted under v1.4 carries a SHA-256 provenance hash that is verifiable against a frozen reference."



\*\*Timing.\*\* Nice to have within \~3-7 days; not blocking the calibration work (we're waiting on clinician responses for that). Happy to jump on a call if anything's unclear.



Many thanks,

\[Your name]

