# AIBL V26.15.0 — HTML / Email / Process Investigation

## Fixed
- Outlook sender selection now uses `MailItem.SendUsingAccount` and fails explicitly if `AIBL_EMAIL_SENDER` is configured but not found.
- Email attachment/body ordering is stabilized with `Save()` before display/send.
- Dashboard now has an explicit Display / Real Send control instead of only generating an email package.

## HTML
- Replaced the legacy static dashboard HTML export with the dynamic Studio HTML engine.
- Persian IRANSans-first typography in generated HTML.
- Interactive filters/search remain active in the exported HTML.
- Added decision-story narrative that updates with the active filter.
- Added richer SVG visuals: donut, horizontal bars, scatter, and process bottleneck view.
- Added Process Explorer with bottlenecks, variants, and conformance root-cause evidence.
- Added a fully client-side XLSX exporter: the Excel file is generated from the exact active HTML filter, without an external CDN.

## Validation
- Python bytecode compilation: passed.
- `tests/test_email_report.py`: 11/11 checks passed.
- `tests/test_html_export_v26_15.py`: passed.

## Operational note
Actual Outlook sending requires Windows + Classic Outlook + `pywin32`, because the package uses Outlook COM for inline CID images and the user's Outlook account/network. On non-Windows systems the HTML/Excel features remain usable, but Outlook COM sending cannot run.
