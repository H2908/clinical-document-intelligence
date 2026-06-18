\*\*Subject:\*\* Quick check-in: two schema migrations from Tuesday



Hi \[Partner name],



Quick check-in on the two schema migration requests I sent on Tuesday — no rush, just keeping things moving on my side:



1\. `partner\_handoffs/2026-06-18-provenance-hash-migration.sql` — adds `provenance\_hash VARCHAR(64)` to `CORE.flag` for the audit-agent tamper-evidence work.



2\. `partner\_handoffs/2026-06-18-bnf-code-entity-migration.sql` — adds `bnf\_code VARCHAR(15)` to `CORE.entity` and updates `SP\_WRITE\_ENTITIES` for BNF drug coding through to the FHIR Medication resources.



Both are small (< 1s of DDL each, no backfill needed). Happy to jump on a 15-minute call if anything is unclear about the diffs, or if you'd prefer I run them under a different role.



Phase 4 L2 is otherwise complete on my side. FHIR builders + bundle assembly + R4B validator all landed and verified end-to-end against pat\_test\_01 (74/74 resources validate against R4B strict). The two migrations are the last items before audit-agent and BNF can land in Snowflake too.



Many thanks,

\[Your name]

