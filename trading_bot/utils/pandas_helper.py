"""
Pandas Helper Utilities
Safely handle pandas Series/scalar conversions to avoid ambiguity errors
"""

import pandas as pd
from typing import Any, Union


def to_scalar(value: Any) -> Union[float, int, None]:
    """
    Convert pandas Series to scalar, or return scalar as-is

    Handles the "truth value of an array is ambiguous" error by
    ensuring all values are scalars before boolean operations.

    Args:
        value: Value that could be a scalar or pandas Series

    Returns:
        Scalar value (float, int, or None)
    """
    # Already None
    if value is None:
        return None

    # Convert Series to scalar
    if hasattr(value, 'iloc'):
        if len(value) == 0:
            return None
        value = value.iloc[0]

    # Handle NaN
    if isinstance(value, float) and pd.isna(value):
        return None

    return value


def safe_isna(value: Any) -> bool:
    """
    Safely check if value is NaN, handling both scalars and Series

    Args:
        value: Value to check

    Returns:
        True if value is NaN or None
    """
    if value is None:
        return True

    # Convert Series to scalar first
    if hasattr(value, 'iloc'):
        if len(value) == 0:
            return True
        value = value.iloc[0]

    # Now safe to check pd.isna on scalar
    return pd.isna(value)


def safe_compare(a: Any, b: Any, op: str) -> bool:
    """
    Safely compare two values that might be Series

    Args:
        a: First value
        b: Second value
        op: Operator ('==', '!=', '<', '>', '<=', '>=')

    Returns:
        Boolean result of comparison
    """
    a = to_scalar(a)
    b = to_scalar(b)

    if a is None or b is None:
        return False

    if op == '==':
        return a == b
    elif op == '!=':
        return a != b
    elif op == '<':
        return a < b
    elif op == '>':
        return a > b
    elif op == '<=':
        return a <= b
    elif op == '>=':
        return a >= b
    else:
        raise ValueError(f"Unknown operator: {op}")
