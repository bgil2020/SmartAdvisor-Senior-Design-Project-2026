"""Acquisition boundary for versioned course-description records."""

from .parser import ParseError, parse_course_detail
from .storage import compare_batches, validate_batch

__all__ = ["ParseError", "compare_batches", "parse_course_detail", "validate_batch"]
