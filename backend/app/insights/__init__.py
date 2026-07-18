"""Department problem-statement insight detectors (see `engine.py`).

Importing this package registers every detector module's `@detector`
functions as a side effect — mirrors `kpi/engine.py`'s `@computer` pattern.
"""
from . import detectors_finance, detectors_hr, detectors_marketing, detectors_ops  # noqa: F401
