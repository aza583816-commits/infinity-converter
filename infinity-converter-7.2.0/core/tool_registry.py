"""Compatibility layer for the pre-7.1 Tool Registry import path.

The source of truth now lives under :mod:`core.tooling` and is split by domain.
This shim intentionally preserves every public import while legacy modules move
to the new boundary incrementally.
"""
from core.tooling import *  # noqa: F401,F403
from core.tooling import _meta_for  # explicit for callers importing the private legacy helper
