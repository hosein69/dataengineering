# -*- coding: utf-8 -*-
"""GSI Streamlit applications (Studio, Dashboard, financial workspace).

A regular package on purpose: the bundled process-mining-ui-kit ships its own
top-level ``app.py``. While ``app/`` was a namespace package, any code path that
put the kit on ``sys.path`` made ``import app.theme`` resolve to that file.
"""
