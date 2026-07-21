"""Vowelchemy: turn conversational speech corpora into analyzable vowel data.

The package is intentionally split into a light-weight *library* (corpus
discovery, normalization, analysis, metrics, visualization) that has only
scientific-Python dependencies, and a Streamlit *app* (``vowelchemy.app``)
that wires the library into an interactive, student-friendly workflow.

Importing :mod:`vowelchemy` does **not** import Streamlit, so the library can
be used from scripts, notebooks, and tests without the UI stack.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
