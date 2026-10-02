# AIBL V26 — Executive Production Release

## What changed

- Executive Stream Insight dashboard with customizable filters and a dedicated critical-case view.
- Group criticality propagation: a BL/order becomes critical when it contains at least one `STOCKOUT` or `CRITICAL` material.
- Root cause is preserved at material level through `BL_CRITICAL_MATERIALS`, `BL_CRITICAL_REASON`, `ORDER_CRITICAL_MATERIALS`, and `ORDER_CRITICAL_REASON`.
- Official daily Excel path/name:
  `YYYY-MM-DD/YYYY-MM-DD_Systemmatic Material.xlsx`
- Outlook Executive Daily Email Pack with 3 inline management charts and the official Excel attachment.
- Email recipients can be overridden by `AIBL_EMAIL_TO`; sender by `AIBL_EMAIL_SENDER`.
- Safe preview mode: `python -m aibl email --no-display`.
- Outlook preview: `python -m aibl email`.
- Real send: `python -m aibl email --send`.
- UI button for generating the executive email HTML package.
- 13 active logical source domains remain part of the pipeline and the 13-sheet Excel dashboard remains the authoritative drill-down artifact.

## Production principle

The email is deliberately a concise decision layer. Detailed material/order/BL causes stay in Excel so executives can move from signal to evidence without losing traceability.
