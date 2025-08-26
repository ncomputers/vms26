"""Compatibility wrapper for legacy imports.

This module re-exports the counting helpers from :mod:`app.vision.counting` so
that tests or callers importing ``vision.counting`` continue to function even
if the application package layout changes.
"""

from app.vision.counting import *  # noqa: F401,F403

