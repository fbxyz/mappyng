"""Base classes for first-class map layers.

A :class:`Layer` is a *description of intent*: it carries its data and
parameters, validates itself, and knows how to draw itself into a map
when asked. It does not touch the SVG at construction time.
"""

from __future__ import annotations

import abc
import copy
from typing import Any


class _Unset:
    """Sentinel for an unset keyword argument.

    Lets a layer expose every option as a named parameter while storing
    only the ones the caller actually set. Omitted options stay out of
    ``params``, so each renderer keeps resolving its own default value
    and serialisation round-trips only explicit choices.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "<unset>"


_UNSET = _Unset()


def collect_set(**kwargs: Any) -> dict[str, Any]:
    """Return only the keyword arguments whose value is not ``_UNSET``."""
    return {k: v for k, v in kwargs.items() if v is not _UNSET}


def _normalize_params(params: dict[str, Any]) -> dict[str, Any]:
    """Convert parameter objects to their plain dict form."""
    from ..border_contrast import BorderContrast
    from ..elements import Legend

    out = dict(params)
    if isinstance(out.get("legend"), Legend):
        out["legend"] = out["legend"].to_dict()
    if isinstance(out.get("border_contrast"), BorderContrast):
        out["border_contrast"] = out["border_contrast"].to_dict()
    return out


class LayerStateError(RuntimeError):
    """Raised when a layer is mutated after it has been rendered.

    A layer's parameters describe an intent that is consumed at render
    time. Once rendered, changing them would silently desynchronise the
    object from the SVG already produced, so :meth:`Layer.update` is
    refused.
    """


class RenderContext:
    """Carries what a :class:`Layer` needs to render itself.

    The context is the decoupling point between a layer and the map: a
    layer never reaches into ``Map`` directly, it goes through the
    context. It transports the host map (whose viewports, CRS,
    internal state and font scaling a layer reaches through).

    Parameters
    ----------
    map : Map
        The host map the layer draws into.
    """

    def __init__(self, map: Any) -> None:  # noqa: A002 - mirrors public name
        self.map = map


# Registry of concrete layer types, keyed by class name, used by
# ``Layer.from_dict`` to reconstruct a layer from its serialised form.
_LAYER_REGISTRY: dict[str, type[Layer]] = {}


def register_layer(cls: type[Layer]) -> type[Layer]:
    """Register a concrete :class:`Layer` subclass for deserialisation.

    Used as a decorator on every concrete layer class so that
    :meth:`Layer.from_dict` can map a serialised ``type`` back to its
    class.
    """
    _LAYER_REGISTRY[cls.__name__] = cls
    return cls


class Layer(abc.ABC):
    """Abstract description of a cartographic layer.

    A layer holds its data (``gdf``) and parameters (``params``) and
    draws nothing until :meth:`render` is called. It is validated at
    construction and at every :meth:`update`.

    Parameters
    ----------
    gdf : GeoDataFrame, optional
        The layer data. Required for data layers (``requires_gdf``);
        ignored by reference layers such as the basemap.
    z_index : int, default 0
        Render order. Layers with equal ``z_index`` keep insertion
        order.
    visible : bool, default True
        Whether the layer is drawn.
    **params
        Layer-specific parameters (see each concrete subclass).

    Attributes
    ----------
    id : str or None
        Identifier, assigned by the map when the layer is added.
    """

    #: Identifier prefix for this layer family.
    kind: str = "layer"
    #: Whether a non-empty ``gdf`` is required at construction.
    requires_gdf: bool = False

    def __init__(self, gdf: Any | None = None, *, z_index: int = 0,
                 visible: bool = True, **params: Any) -> None:
        if self.requires_gdf and (gdf is None or getattr(gdf, "empty", False)):
            raise ValueError(
                f"{type(self).__name__} is a data layer and needs a "
                f"non-empty GeoDataFrame. None or an empty frame was "
                f"given, so there is nothing to map. Pass the data as the "
                f"first argument: {type(self).__name__}(gdf, ...)."
            )
        self.gdf = gdf
        self.z_index = z_index
        self.visible = visible
        self.params: dict[str, Any] = _normalize_params(params)
        self.id: str | None = None
        self._rendered = False
        self.validate()

    # -- lifecycle ----------------------------------------------------

    def validate(self) -> None:  # noqa: B027 - optional hook, not abstract
        """Check internal consistency. Override in subclasses.

        Raises in plain language (see ``errors.py`` convention) for
        structural problems such as a missing required parameter.
        Semiological advice is emitted as a warning, never an error.
        """

    @abc.abstractmethod
    def render(self, ctx: RenderContext) -> None:
        """Draw the layer into the map carried by ``ctx``.

        Called when the map is built. Implementations must set
        ``self._rendered = True`` once drawn.
        """

    def update(self, **kwargs: Any) -> Layer:
        """Update parameters and re-validate. Returns ``self``.

        ``z_index`` and ``visible`` are treated as layer metadata; any
        other keyword updates :attr:`params`.

        Raises
        ------
        LayerStateError
            If the layer has already been rendered.
        """
        if self._rendered:
            raise LayerStateError(
                f"{type(self).__name__}(id={self.id!r}) has already been "
                f"rendered; its parameters are now fixed. Build a fresh "
                f"layer instead of mutating a rendered one."
            )
        for meta in ("z_index", "visible"):
            if meta in kwargs:
                setattr(self, meta, kwargs.pop(meta))
        self.params.update(_normalize_params(kwargs))
        self.validate()
        return self

    def copy(self) -> Layer:
        """Return an unrendered copy that shares the same data.

        The parameters are copied, the GeoDataFrame is shared. The copy
        has no ``id`` until it is added to a map.
        """
        new = copy.copy(self)
        new.params = dict(self.params)
        new.id = None
        new._rendered = False
        if hasattr(new, "report"):
            new.report = None  # a copy has not been drawn yet
        return new

    # -- serialisation ------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise the layer's intent (not its geometry).

        The geometry is flagged by ``data['in_memory']``; persisting it
        by reference or path is handled by serialisation.
        """
        return {
            "type": self.type_name(),
            "id": self.id,
            "z_index": self.z_index,
            "visible": self.visible,
            "params": dict(self.params),
            "data": {"in_memory": self.gdf is not None},
        }

    @classmethod
    def type_name(cls) -> str:
        """Name under which the layer type is registered."""
        for klass in cls.__mro__:
            if _LAYER_REGISTRY.get(klass.__name__) is klass:
                return klass.__name__
        return cls.__name__

    @classmethod
    def from_dict(cls, data: dict[str, Any],
                  gdf: Any | None = None) -> Layer:
        """Rebuild a layer from :meth:`to_dict` output.

        Parameters
        ----------
        data : dict
            A serialised layer.
        gdf : GeoDataFrame, optional
            Geometry to reattach (the serialised form does not carry it).
        """
        type_name = data.get("type")
        target = (_LAYER_REGISTRY.get(type_name)
                  if type_name is not None else None)
        if target is None:
            renamed = ""
            if (isinstance(type_name, str) and type_name.endswith("Layer")
                    and type_name[:-len("Layer")] in _LAYER_REGISTRY):
                new_name = type_name[:-len("Layer")]
                renamed = (f" {type_name!r} was renamed {new_name!r} in "
                           f"mappyng 2.0: edit the 'type' of the layer.")
            raise ValueError(
                f"Unknown layer type {type_name!r}.{renamed} Known types: "
                f"{sorted(_LAYER_REGISTRY)}. The serialised data may come "
                f"from a newer mappyng or a custom layer that is not "
                f"imported."
            )
        obj = target(gdf, z_index=data.get("z_index", 0),
                     visible=data.get("visible", True),
                     **dict(data.get("params", {})))
        obj.id = data.get("id")
        return obj

    def __repr__(self) -> str:
        return (f"{type(self).__name__}(id={self.id!r}, "
                f"z_index={self.z_index}, params={self.params!r})")
