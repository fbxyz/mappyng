from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from pyproj.exceptions import ProjError
from shapely.errors import GEOSException

#: Exceptions raised by reprojection (bad or missing CRS) and by geometry
#: operations such as clipping. Use instead of a bare ``except Exception``
#: where a geometry/CRS failure has a sensible fallback.
GEO_ERRORS = (ValueError, ProjError, GEOSException)

F = TypeVar('F', bound=Callable[..., Any])


class MapError(Exception):
    """Base exception for all mappyng-related errors."""
    pass


class RenderError(MapError):
    """Raised when an error occurs during SVG rendering."""
    pass


class CartoucheError(MapError):
    """Raised when an error occurs in cartouche/inset operations."""
    pass


class DataError(MapError):
    """Raised for input data issues (missing columns, invalid CRS, bad geometry)."""
    pass


class LayoutError(MapError):
    """Raised for layout element errors (title, scale bar, legend, source)."""
    pass


def handle_map_errors(func: F) -> F:
    """Decorator that wraps map operations to provide consistent error context."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except (DataError, RenderError, CartoucheError, LayoutError) as e:
            raise type(e)(f"{type(e).__name__} in {func.__name__}: {str(e)}") from e
        except MapError:
            raise
        except Exception as e:
            raise MapError(f"Unexpected error in {func.__name__}: {str(e)}") from e

    return wrapper  # type: ignore
