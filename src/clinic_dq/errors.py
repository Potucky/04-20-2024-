"""Failures that mean the run could not be evaluated."""


class DQError(Exception):
    """Configuration, load, or usage error. The CLI exits 2."""
