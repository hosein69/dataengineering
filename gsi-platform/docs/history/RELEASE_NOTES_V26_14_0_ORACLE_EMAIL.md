# AIBL V26.14.0 — Oracle reconciliation + Excel email charts + fast HTML

- Oracle adapter now compares all loaded sheets and reconciles fields per material.
- More-complete sheet values are preferred, with field-level fallback from other sheets.
- `ORC_SOURCE_SHEET` and completeness score preserve provenance.
- Email chart catalog remains Persian; Studio Excel exports now include a native `Email Charts` sheet with editable Excel charts and Persian labels.
- HTML default payload is reduced for faster browser startup; large event-log payloads are no longer embedded in the interactive HTML.
- Excel remains the detailed/auditable output.
