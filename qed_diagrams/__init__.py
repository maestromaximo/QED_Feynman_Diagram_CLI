"""Lowest-order QED Feynman diagram generator."""

from .amplitude import generate_symbolic_amplitudes
from .core import DiagramGenerationError, generate_diagrams, parse_reaction
from .custom_theory import DEFAULT_CUSTOM_THEORY, generate_custom_theory_diagrams, parse_custom_theory
from .render import render_diagram_svg

__all__ = [
    "DEFAULT_CUSTOM_THEORY",
    "DiagramGenerationError",
    "generate_custom_theory_diagrams",
    "generate_symbolic_amplitudes",
    "generate_diagrams",
    "parse_custom_theory",
    "parse_reaction",
    "render_diagram_svg",
]
