"""
woundtrack.utils
================

Generic helper functions with no domain-specific logic.
These utilities are used across the woundtrack library.
"""

from typing import Optional, Tuple, Union

import numpy as np

__all__ = [
    "ensure_binary_mask",
    "validate_2d_array",
    "safe_divide",
    "normalize_to_01",
]


def ensure_binary_mask(
    mask: np.ndarray,
    dtype: np.dtype = np.uint8,
) -> np.ndarray:
    """
    Normalize a mask to binary format (0/1).

    Parameters
    ----------
    mask : np.ndarray
        Input mask, can be boolean, integer, or float.
    dtype : np.dtype
        Output dtype (default: uint8).

    Returns
    -------
    np.ndarray
        Binary mask with values 0 and 1 only.

    Examples
    --------
    >>> mask = np.array([[0, 255], [1, 0]])
    >>> ensure_binary_mask(mask)
    array([[0, 1],
           [1, 0]], dtype=uint8)
    """
    arr = np.asarray(mask)
    return (arr > 0).astype(dtype)


def validate_2d_array(
    arr: np.ndarray,
    name: str = "array",
    allow_none: bool = False,
) -> Optional[np.ndarray]:
    """
    Validate that an array is 2D.

    Parameters
    ----------
    arr : np.ndarray
        Array to validate.
    name : str
        Name of the array for error messages.
    allow_none : bool
        If True, None is accepted and returned as-is.

    Returns
    -------
    np.ndarray or None
        The validated array.

    Raises
    ------
    ValueError
        If array is not 2D (and not None when allow_none=True).
    """
    if arr is None:
        if allow_none:
            return None
        raise ValueError(f"{name} cannot be None")
    
    arr = np.asarray(arr)
    if arr.ndim != 2:
        raise ValueError(f"{name} must be 2D, got shape {arr.shape}")
    
    return arr


def safe_divide(
    numerator: Union[float, np.ndarray],
    denominator: Union[float, np.ndarray],
    fill_value: float = 0.0,
) -> Union[float, np.ndarray]:
    """
    Safely divide, returning fill_value where denominator is zero.

    Parameters
    ----------
    numerator : float or np.ndarray
        Numerator value(s).
    denominator : float or np.ndarray
        Denominator value(s).
    fill_value : float
        Value to use where denominator is zero.

    Returns
    -------
    float or np.ndarray
        Result of division with fill_value where denominator was zero.
    """
    num = np.asarray(numerator, dtype=float)
    denom = np.asarray(denominator, dtype=float)
    
    with np.errstate(divide='ignore', invalid='ignore'):
        result = np.true_divide(num, denom)
        result = np.where(denom == 0, fill_value, result)
    
    # Return scalar if inputs were scalar
    if np.ndim(numerator) == 0 and np.ndim(denominator) == 0:
        return float(result)
    return result


def normalize_to_01(
    arr: np.ndarray,
    eps: float = 1e-8,
) -> np.ndarray:
    """
    Normalize array values to [0, 1] range.

    Parameters
    ----------
    arr : np.ndarray
        Input array.
    eps : float
        Small value to prevent division by zero.

    Returns
    -------
    np.ndarray
        Array with values in [0, 1] range.
    """
    arr = np.asarray(arr, dtype=float)
    arr_min = arr.min()
    arr_max = arr.max()
    return (arr - arr_min) / (arr_max - arr_min + eps)
