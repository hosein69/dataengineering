# Browser reproduction notes

Browser evidence was produced with Playwright and @sparticuz/chromium 153.0.0, temporarily installed for QA. Browser binaries/node_modules are deliberately excluded. The recorded scripts use the authoring-workspace relative layout; set their browser executable and preview paths to your local installation when rerunning. Run make_preview.py from the parent of a final_src checkout, or adapt that path. Streamlit browser QA requires the local server in the same network namespace; the recorded run used an empty disposable DWH, not production data.

Exported HTML checks are synthetic. Streamlit checks exercised four tabs with no exception or browser page error in an empty published-source scenario. Screenshots visually inspected. These checks do not certify financial source completeness.
