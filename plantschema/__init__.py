"""plantschema — anlagen-neutrale semantische Anlagen-Schemas → deterministisches SVG.

Pipeline: parse → validate → route → place → emit → write
(Sprint S1: Walking Skeleton über alle Stufen, Minimum-funktional.)
"""

from .model import (
    Canvas,
    Component,
    Label,
    LabelSpec,
    Pipe,
    PipeKind,
    PortRef,
    Readout,
    ReadoutAt,
    Schema,
    SchemaError,
    TextAnchor,
)

__version__ = "0.1.0"

__all__ = [
    "Canvas",
    "Component",
    "Label",
    "LabelSpec",
    "Pipe",
    "PipeKind",
    "PortRef",
    "Readout",
    "ReadoutAt",
    "Schema",
    "SchemaError",
    "TextAnchor",
    "__version__",
]
