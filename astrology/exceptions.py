"""Custom domain and integrity exceptions for astrology pipeline."""

class AstrologyError(Exception):
    """Base class for exceptions in this package."""
    pass


class BenchmarkIntegrityError(AstrologyError):
    """Raised when benchmark artifact hashes or files fail integrity checks."""
    pass


class LineageMismatchError(AstrologyError):
    """Raised when packet_id or snapshot metadata mismatches between pipeline stages."""
    pass


class SelectionPlanValidationError(AstrologyError):
    """Raised when Author-owned ReaderSelectionPlan violates structure, coverage or ancestry."""
    pass


class ReviewerAuthorityBoundaryError(AstrologyError):
    """Raised when Reviewer violates Author materialized provenance or inserts unearned sources."""
    pass
