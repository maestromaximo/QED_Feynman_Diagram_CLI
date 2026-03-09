from __future__ import annotations

from dataclasses import dataclass
import html
import math

from .core import Diagram, DiagramBundle, ExternalLeg


@dataclass(frozen=True)
class RenderOptions:
    compact: bool = False
    show_leg_ids: bool = False
    show_momenta: bool = True


def render_diagram_svg(
    bundle: DiagramBundle,
    diagram: Diagram,
    options: RenderOptions | None = None,
) -> str:
    options = options or RenderOptions()
    legs = {leg.identifier: leg for leg in bundle.reaction.all_legs}
    width = 860 if options.compact else 980
    height = 440 if options.compact else 520

    points = _points_for_template(diagram.template, width, height, legs)
    vertex_a = points["vertex_a"]
    vertex_b = points["vertex_b"]

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{html.escape(diagram.title)}">',
        "<defs>",
        '<style>'
        ".bg{fill:#f7f1e1;}"
        ".panel{fill:#fffdf5;stroke:#d6c7a3;stroke-width:2.2;}"
        ".vertex{fill:#1f2a1f;}"
        ".fermion{stroke:#1f2a1f;stroke-width:3.6;fill:none;stroke-linecap:round;}"
        ".photon{stroke:#8f2d1b;stroke-width:3.2;fill:none;stroke-linecap:round;stroke-linejoin:round;}"
        ".scalar{stroke:#59644f;stroke-width:3.2;fill:none;stroke-linecap:round;stroke-dasharray:10 8;}"
        ".arrow{stroke:#1f2a1f;stroke-width:2.6;fill:none;stroke-linecap:round;stroke-linejoin:round;}"
        ".particle{font:700 18px 'Trebuchet MS','Segoe UI',sans-serif;fill:#1f2a1f;}"
        ".momentum{font:600 13px 'Trebuchet MS','Segoe UI',sans-serif;fill:#5a6654;}"
        ".meta{font:700 12px 'Trebuchet MS','Segoe UI',sans-serif;letter-spacing:.12em;text-transform:uppercase;fill:#8f2d1b;}"
        ".legend{font:600 14px 'Trebuchet MS','Segoe UI',sans-serif;fill:#4a5647;}"
        "</style>",
        "</defs>",
        f'<rect class="bg" x="0" y="0" width="{width}" height="{height}" rx="30" />',
        f'<rect class="panel" x="20" y="20" width="{width - 40}" height="{height - 40}" rx="28" />',
        f'<text class="meta" x="48" y="56">{html.escape(diagram.order)} diagram</text>',
        f'<text class="legend" x="{width - 198}" y="{height - 34}">Time flows upward</text>',
    ]

    for leg_id in diagram.vertex_a:
        svg.extend(_draw_external_edge(legs[leg_id], points, vertex_a, options))
    for leg_id in diagram.vertex_b:
        svg.extend(_draw_external_edge(legs[leg_id], points, vertex_b, options))

    if diagram.topology in {"photon_exchange", "vector_exchange"}:
        svg.extend(_draw_internal_photon(diagram, vertex_a, vertex_b, options))
    elif diagram.topology == "scalar_exchange":
        svg.extend(_draw_internal_scalar(diagram, vertex_a, vertex_b, options))
    else:
        svg.extend(_draw_internal_fermion(diagram, vertex_a, vertex_b, options))

    svg.append(f'<circle class="vertex" cx="{vertex_a[0]}" cy="{vertex_a[1]}" r="6" />')
    svg.append(f'<circle class="vertex" cx="{vertex_b[0]}" cy="{vertex_b[1]}" r="6" />')
    svg.append("</svg>")
    return "".join(svg)


def _points_for_template(
    template: str,
    width: int,
    height: int,
    legs: dict[str, ExternalLeg],
) -> dict[str, tuple[float, float]]:
    if template == "photon_vertical":
        return {
            "vertex_a": (width * 0.50, height * 0.70),
            "vertex_b": (width * 0.50, height * 0.34),
            "in1": (width * 0.18, height * 0.84),
            "in2": (width * 0.82, height * 0.84),
            "out1": (width * 0.18, height * 0.16),
            "out2": (width * 0.82, height * 0.16),
        }
    if template == "photon_horizontal":
        return {
            "vertex_a": (width * 0.34, height * 0.55),
            "vertex_b": (width * 0.66, height * 0.55),
            "in1": (width * 0.18, height * 0.84),
            "in2": (width * 0.82, height * 0.84),
            "out1": (width * 0.18, height * 0.16),
            "out2": (width * 0.82, height * 0.16),
        }
    if template == "fermion_compton":
        incoming_charge = next(
            leg.identifier
            for leg in legs.values()
            if leg.side == "incoming" and leg.particle.kind == "fermion"
        )
        incoming_photon = next(
            leg.identifier
            for leg in legs.values()
            if leg.side == "incoming" and leg.particle.kind == "photon"
        )
        outgoing_charge = next(
            leg.identifier
            for leg in legs.values()
            if leg.side == "outgoing" and leg.particle.kind == "fermion"
        )
        outgoing_photon = next(
            leg.identifier
            for leg in legs.values()
            if leg.side == "outgoing" and leg.particle.kind == "photon"
        )
        return {
            "vertex_a": (width * 0.36, height * 0.60),
            "vertex_b": (width * 0.64, height * 0.46),
            incoming_charge: (width * 0.16, height * 0.82),
            incoming_photon: (width * 0.84, height * 0.82),
            outgoing_photon: (width * 0.16, height * 0.16),
            outgoing_charge: (width * 0.84, height * 0.16),
        }
    if template == "fermion_annihilation":
        return {
            "vertex_a": (width * 0.34, height * 0.60),
            "vertex_b": (width * 0.66, height * 0.60),
            "in1": (width * 0.18, height * 0.84),
            "in2": (width * 0.82, height * 0.84),
            "out1": (width * 0.18, height * 0.16),
            "out2": (width * 0.82, height * 0.16),
        }
    return {
        "vertex_a": (width * 0.34, height * 0.42),
        "vertex_b": (width * 0.66, height * 0.42),
        "in1": (width * 0.18, height * 0.84),
        "in2": (width * 0.82, height * 0.84),
        "out1": (width * 0.18, height * 0.16),
        "out2": (width * 0.82, height * 0.16),
    }


def _draw_external_edge(
    leg: ExternalLeg,
    points: dict[str, tuple[float, float]],
    vertex: tuple[float, float],
    options: RenderOptions,
) -> list[str]:
    anchor = points[leg.identifier]
    particle_x, particle_y = _particle_label_position(anchor, vertex, leg.side)
    particle_label = leg.particle.label if not options.show_leg_ids else f"{leg.identifier} {leg.particle.label}"

    if leg.particle.kind in {"photon", "vector"}:
        edge_parts = _draw_photon(anchor, vertex)
    elif leg.particle.kind == "scalar":
        edge_parts = _draw_scalar(anchor, vertex)
    else:
        edge_parts = _draw_fermion(anchor, vertex, leg.arrow_toward_vertex)

    edge_parts.append(
        f'<text class="particle" x="{particle_x}" y="{particle_y}" text-anchor="{_label_align(anchor)}">'
        f"{html.escape(particle_label)}</text>"
    )
    if options.show_momenta:
        momentum_x, momentum_y = _momentum_label_position(anchor, vertex, leg.side)
        edge_parts.append(
            f'<text class="momentum" x="{momentum_x}" y="{momentum_y}" text-anchor="middle">'
            f"{html.escape(leg.momentum_label)}</text>"
        )
    return edge_parts


def _draw_internal_photon(
    diagram: Diagram,
    vertex_a: tuple[float, float],
    vertex_b: tuple[float, float],
    options: RenderOptions,
) -> list[str]:
    if diagram.correction == "vacuum_polarization":
        return _draw_vacuum_polarization(diagram, vertex_a, vertex_b, options)

    parts = _draw_photon(vertex_a, vertex_b)
    if options.show_momenta:
        label_x, label_y = _mid_label_position(vertex_a, vertex_b, -18)
        parts.append(
            f'<text class="momentum" x="{label_x}" y="{label_y}" text-anchor="middle">'
            f"{html.escape(diagram.internal_momentum)}</text>"
            "</text>"
        )
    return parts


def _draw_vacuum_polarization(
    diagram: Diagram,
    vertex_a: tuple[float, float],
    vertex_b: tuple[float, float],
    options: RenderOptions,
) -> list[str]:
    center = ((vertex_a[0] + vertex_b[0]) / 2, (vertex_a[1] + vertex_b[1]) / 2)
    ux, uy, nx, ny, _ = _geometry(vertex_a, vertex_b)
    bubble_half = 34
    bubble_height = 44
    left = (center[0] - ux * bubble_half, center[1] - uy * bubble_half)
    right = (center[0] + ux * bubble_half, center[1] + uy * bubble_half)
    upper_control = (center[0] + nx * bubble_height, center[1] + ny * bubble_height)
    lower_control = (center[0] - nx * bubble_height, center[1] - ny * bubble_height)

    parts = []
    parts.extend(_draw_photon(vertex_a, left))
    parts.extend(_draw_photon(right, vertex_b))
    parts.append(
        f'<path class="fermion" d="M {left[0]:.2f} {left[1]:.2f} '
        f'Q {upper_control[0]:.2f} {upper_control[1]:.2f} {right[0]:.2f} {right[1]:.2f}" />'
    )
    parts.append(
        _quadratic_arrow_segment(left, upper_control, right, forward=True)
    )
    parts.append(
        f'<path class="fermion" d="M {right[0]:.2f} {right[1]:.2f} '
        f'Q {lower_control[0]:.2f} {lower_control[1]:.2f} {left[0]:.2f} {left[1]:.2f}" />'
    )
    parts.append(
        _quadratic_arrow_segment(right, lower_control, left, forward=True)
    )
    if options.show_momenta:
        qx, qy = _mid_label_position(vertex_a, vertex_b, -18)
        loop_x = center[0] + nx * 62
        loop_y = center[1] + ny * 62
        parts.append(
            f'<text class="momentum" x="{qx}" y="{qy}" text-anchor="middle">'
            f"{html.escape(diagram.internal_momentum)}</text>"
        )
        parts.append(
            f'<text class="momentum" x="{loop_x:.2f}" y="{loop_y:.2f}" text-anchor="middle">'
            f"{html.escape(diagram.loop_momentum or 'ell1')}</text>"
        )
    return parts


def _draw_internal_fermion(
    diagram: Diagram,
    vertex_a: tuple[float, float],
    vertex_b: tuple[float, float],
    options: RenderOptions,
) -> list[str]:
    parts = [
        f'<line class="fermion" x1="{vertex_a[0]}" y1="{vertex_a[1]}" x2="{vertex_b[0]}" y2="{vertex_b[1]}" />',
        _arrow_segment(vertex_a, vertex_b),
    ]
    if options.show_momenta:
        label_x, label_y = _mid_label_position(vertex_a, vertex_b, -18)
        parts.append(
            f'<text class="momentum" x="{label_x}" y="{label_y}" text-anchor="middle">'
            f"{html.escape(diagram.internal_momentum)}</text>"
        )
    return parts


def _draw_internal_scalar(
    diagram: Diagram,
    vertex_a: tuple[float, float],
    vertex_b: tuple[float, float],
    options: RenderOptions,
) -> list[str]:
    parts = _draw_scalar(vertex_a, vertex_b)
    if options.show_momenta:
        label_x, label_y = _mid_label_position(vertex_a, vertex_b, -18)
        parts.append(
            f'<text class="momentum" x="{label_x}" y="{label_y}" text-anchor="middle">'
            f"{html.escape(diagram.internal_momentum)}</text>"
        )
    return parts


def _draw_fermion(
    anchor: tuple[float, float],
    vertex: tuple[float, float],
    arrow_toward_vertex: bool | None,
) -> list[str]:
    start, end = (anchor, vertex) if arrow_toward_vertex else (vertex, anchor)
    return [
        f'<line class="fermion" x1="{start[0]}" y1="{start[1]}" x2="{end[0]}" y2="{end[1]}" />',
        _arrow_segment(start, end),
    ]


def _draw_photon(
    start: tuple[float, float],
    end: tuple[float, float],
) -> list[str]:
    points = _wavy_points(start, end, amplitude=8, wavelength=22)
    path = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in points)
    return [f'<path class="photon" d="{path}" />']


def _draw_scalar(
    start: tuple[float, float],
    end: tuple[float, float],
) -> list[str]:
    return [
        f'<line class="scalar" x1="{start[0]}" y1="{start[1]}" x2="{end[0]}" y2="{end[1]}" />'
    ]


def _wavy_points(
    start: tuple[float, float],
    end: tuple[float, float],
    amplitude: float,
    wavelength: float,
) -> list[tuple[float, float]]:
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return [start, end]

    ux = dx / length
    uy = dy / length
    nx = -uy
    ny = ux
    steps = max(16, int(length / 8))

    points = []
    for step in range(steps + 1):
        t = step / steps
        phase = math.sin((length * t / wavelength) * 2 * math.pi)
        offset = amplitude * phase
        px = x1 + dx * t + nx * offset
        py = y1 + dy * t + ny * offset
        points.append((px, py))
    return points


def _arrow_segment(start: tuple[float, float], end: tuple[float, float]) -> str:
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length < 14:
        return ""

    ux = dx / length
    uy = dy / length
    center_x = x1 + dx * 0.56
    center_y = y1 + dy * 0.56
    tail_x = center_x - ux * 13
    tail_y = center_y - uy * 13
    head_x = center_x + ux * 13
    head_y = center_y + uy * 13
    left_x = head_x - ux * 8 - uy * 6
    left_y = head_y - uy * 8 + ux * 6
    right_x = head_x - ux * 8 + uy * 6
    right_y = head_y - uy * 8 - ux * 6

    return (
        f'<path class="arrow" d="M {tail_x:.2f} {tail_y:.2f} L {head_x:.2f} {head_y:.2f} '
        f'M {left_x:.2f} {left_y:.2f} L {head_x:.2f} {head_y:.2f} '
        f'L {right_x:.2f} {right_y:.2f}" />'
    )


def _quadratic_arrow_segment(
    start: tuple[float, float],
    control: tuple[float, float],
    end: tuple[float, float],
    forward: bool,
) -> str:
    t = 0.58
    x = (1 - t) ** 2 * start[0] + 2 * (1 - t) * t * control[0] + t**2 * end[0]
    y = (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * control[1] + t**2 * end[1]
    dx = 2 * (1 - t) * (control[0] - start[0]) + 2 * t * (end[0] - control[0])
    dy = 2 * (1 - t) * (control[1] - start[1]) + 2 * t * (end[1] - control[1])
    if not forward:
        dx *= -1
        dy *= -1
    length = math.hypot(dx, dy)
    if length == 0:
        return ""
    ux = dx / length
    uy = dy / length
    tail = (x - ux * 11, y - uy * 11)
    head = (x + ux * 11, y + uy * 11)
    left = (head[0] - ux * 7 - uy * 5, head[1] - uy * 7 + ux * 5)
    right = (head[0] - ux * 7 + uy * 5, head[1] - uy * 7 - ux * 5)
    return (
        f'<path class="arrow" d="M {tail[0]:.2f} {tail[1]:.2f} L {head[0]:.2f} {head[1]:.2f} '
        f'M {left[0]:.2f} {left[1]:.2f} L {head[0]:.2f} {head[1]:.2f} '
        f'L {right[0]:.2f} {right[1]:.2f}" />'
    )


def _particle_label_position(
    anchor: tuple[float, float],
    vertex: tuple[float, float],
    side: str,
) -> tuple[float, float]:
    x, y = anchor
    vx, vy = vertex
    shift_x = -22 if x < vx else 22
    shift_y = 22 if side == "incoming" else -18
    return x + shift_x, y + shift_y


def _momentum_label_position(
    anchor: tuple[float, float],
    vertex: tuple[float, float],
    side: str,
) -> tuple[float, float]:
    dx = vertex[0] - anchor[0]
    dy = vertex[1] - anchor[1]
    length = math.hypot(dx, dy) or 1.0
    nx = -dy / length
    ny = dx / length
    t = 0.46 if side == "incoming" else 0.54
    base_x = anchor[0] + dx * t
    base_y = anchor[1] + dy * t
    direction = -1 if anchor[0] < vertex[0] else 1
    return base_x + nx * 14 * direction, base_y + ny * 14 * direction


def _mid_label_position(
    start: tuple[float, float],
    end: tuple[float, float],
    offset: float,
) -> tuple[float, float]:
    ux, uy, nx, ny, _ = _geometry(start, end)
    center_x = (start[0] + end[0]) / 2
    center_y = (start[1] + end[1]) / 2
    return center_x + nx * offset, center_y + ny * offset


def _geometry(
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[float, float, float, float, float]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy) or 1.0
    ux = dx / length
    uy = dy / length
    nx = -uy
    ny = ux
    return ux, uy, nx, ny, length


def _label_align(anchor: tuple[float, float]) -> str:
    return "end" if anchor[0] < 490 else "start"
