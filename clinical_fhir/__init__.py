"""FHIR R4 resource builders for Clinical Document Intelligence.

Maps internal data shapes (CORE.patient, CORE.entity, CORE.observation)
to FHIR R4 JSON resources. Pure functions, no I/O.

Out of scope: AllergyIntolerance, Encounter, FHIR R5, POST endpoint.
"""