import pytest

from mappyng import (
    CartoucheError,
    DataError,
    LayoutError,
    MapError,
    RenderError,
    handle_map_errors,
)


def test_imports():
    assert MapError
    assert RenderError
    assert DataError
    assert LayoutError
    assert CartoucheError
    assert handle_map_errors


def test_hierarchy():
    assert issubclass(RenderError, MapError)
    assert issubclass(CartoucheError, MapError)
    assert issubclass(DataError, MapError)
    assert issubclass(LayoutError, MapError)


def test_catch_all_with_base():
    with pytest.raises(MapError):
        raise DataError("missing column")

    with pytest.raises(MapError):
        raise RenderError("bad colormap")


def test_decorator_passthrough():
    @handle_map_errors
    def ok():
        return 42

    assert ok() == 42


def test_decorator_rewraps_known():
    @handle_map_errors
    def bad():
        raise DataError("invalid CRS")

    with pytest.raises(DataError, match="DataError in bad: invalid CRS"):
        bad()


def test_decorator_rewraps_layout():
    @handle_map_errors
    def bad():
        raise LayoutError("negative scale")

    with pytest.raises(LayoutError, match="LayoutError in bad: negative scale"):
        bad()


def test_decorator_wraps_unexpected():
    @handle_map_errors
    def bad():
        raise ValueError("oops")

    with pytest.raises(MapError, match="Unexpected error in bad: oops"):
        bad()


def test_decorator_passes_map_error_subclass_untouched():
    # MapError itself (not a known subclass) should pass through as-is
    @handle_map_errors
    def bad():
        raise MapError("direct base")

    with pytest.raises(MapError, match="direct base"):
        bad()
