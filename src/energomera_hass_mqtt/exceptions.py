"""
Exceptions for the package.
"""


class EnergomeraConfigError(Exception):
    """
    Exception thrown when configuration processing encounters an error.
    """


class EnergomeraMeterError(Exception):
    """
    Exception thrown when the energy meter communication fails.
    """
