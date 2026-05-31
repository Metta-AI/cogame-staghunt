"""stag_hunt Coworld supporting runnables: grader and reporter.

Both consume a Coworld episode bundle and are reward-agnostic — see
``episode.py``. Entrypoints:

  python -m staghunt_tools.grader     # writes a grade JSON to COGAME_GRADE_URI
  python -m staghunt_tools.reporter   # writes a report zip to COGAME_REPORT_URI
"""
