from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import re

from .core import Diagram, DiagramBundle, DiagramGenerationError, ExternalLeg, Reaction


REACTION_SPLIT_RE = re.compile(r"\s*(?:->|=>)\s*")

DEFAULT_CUSTOM_THEORY = """{
  "name": "Electron-pseudoscalar Yukawa theory",
  "particles": [
    {"token": "e-", "label": "e-", "kind": "fermion", "family": "electron", "charge": -1, "anti": false, "mass_symbol": "m_e"},
    {"token": "e+", "label": "e+", "kind": "fermion", "family": "electron", "charge": 1, "anti": true, "mass_symbol": "m_e"},
    {"token": "phi", "label": "φ", "kind": "scalar", "family": "phi", "charge": 0, "mass_symbol": "0"}
  ],
  "vertices": [
    {"name": "e-e+phi", "fields": ["e-", "e+", "phi"], "factor": "i g \\\\gamma^5"}
  ]
}"""


@dataclass(frozen=True)
class TheoryParticle:
    token: str
    label: str
    kind: str
    family: str | None
    charge: int
    mass_symbol: str | None = None
    anti: bool = False


@dataclass(frozen=True)
class TheoryVertex:
    name: str
    fields: tuple[str, ...]
    factor: str = ""


@dataclass(frozen=True)
class CustomTheory:
    name: str
    particles: dict[str, TheoryParticle]
    vertices: tuple[TheoryVertex, ...]


@dataclass(frozen=True)
class CustomAmplitudeTerm:
    index: int
    label: str
    sign: int
    expression: str
    annotated_expression: str


@dataclass(frozen=True)
class CustomSymbolicAmplitude:
    reaction: str
    order: str
    terms: tuple[CustomAmplitudeTerm, ...]
    total_expression: str
    total_annotated_expression: str
    notes: tuple[str, ...]


def generate_custom_theory_diagrams(theory_text: str, reaction_raw: str) -> tuple[CustomTheory, DiagramBundle]:
    theory = parse_custom_theory(theory_text)
    reaction = parse_custom_reaction(theory, reaction_raw)

    if len(reaction.incoming) != 2 or len(reaction.outgoing) != 2:
        raise DiagramGenerationError(
            "Custom-theory mode currently supports tree-level 2->2 reactions only."
        )

    diagrams = _generate_tree_diagrams(theory, reaction)
    if not diagrams:
        raise DiagramGenerationError(
            "No connected tree-level 2->2 diagrams were found with the supplied 3-point vertices."
        )

    notes = [
        f"Theory: {theory.name}",
        "Custom-theory mode currently builds connected tree-level 2->2 diagrams from two 3-point vertices.",
    ]
    return theory, DiagramBundle(reaction=reaction, order="tree", diagrams=diagrams, notes=tuple(notes))


def parse_custom_theory(theory_text: str) -> CustomTheory:
    try:
        data = json.loads(theory_text)
    except json.JSONDecodeError as exc:
        raise DiagramGenerationError(f"Custom theory JSON is invalid: {exc.msg}.") from exc

    if not isinstance(data, dict):
        raise DiagramGenerationError("Custom theory must be a JSON object.")

    particles_raw = data.get("particles")
    vertices_raw = data.get("vertices")
    if not isinstance(particles_raw, list) or not particles_raw:
        raise DiagramGenerationError("Custom theory must define a non-empty 'particles' list.")
    if not isinstance(vertices_raw, list) or not vertices_raw:
        raise DiagramGenerationError("Custom theory must define a non-empty 'vertices' list.")

    particles: dict[str, TheoryParticle] = {}
    for entry in particles_raw:
        if not isinstance(entry, dict):
            raise DiagramGenerationError("Each particle definition must be an object.")
        token = str(entry.get("token", "")).strip()
        if not token:
            raise DiagramGenerationError("Each particle definition requires a non-empty 'token'.")
        kind = str(entry.get("kind", "")).strip().lower()
        if kind not in {"fermion", "scalar", "vector", "photon"}:
            raise DiagramGenerationError(
                f"Unsupported particle kind '{kind}' for token '{token}'. Use fermion, scalar, or vector."
            )
        particles[token] = TheoryParticle(
            token=token,
            label=str(entry.get("label", token)),
            kind=kind,
            family=(str(entry.get("family")).strip() if entry.get("family") is not None else None),
            charge=int(entry.get("charge", 0)),
            mass_symbol=(str(entry.get("mass_symbol")).strip() if entry.get("mass_symbol") is not None else None),
            anti=bool(entry.get("anti", False)),
        )

    vertices = []
    for entry in vertices_raw:
        if not isinstance(entry, dict):
            raise DiagramGenerationError("Each vertex definition must be an object.")
        name = str(entry.get("name", "")).strip() or "vertex"
        fields = entry.get("fields")
        if not isinstance(fields, list) or len(fields) != 3:
            raise DiagramGenerationError(f"Vertex '{name}' must define exactly three field tokens.")
        field_tokens = tuple(str(field).strip() for field in fields)
        if any(token not in particles for token in field_tokens):
            raise DiagramGenerationError(f"Vertex '{name}' references an undefined particle token.")
        vertices.append(
            TheoryVertex(
                name=name,
                fields=field_tokens,
                factor=str(entry.get("factor", "")).strip(),
            )
        )

    return CustomTheory(
        name=str(data.get("name", "Custom theory")).strip() or "Custom theory",
        particles=particles,
        vertices=tuple(vertices),
    )


def generate_custom_symbolic_amplitudes(
    theory_text: str,
    reaction_raw: str,
) -> tuple[CustomTheory, DiagramBundle, CustomSymbolicAmplitude]:
    theory, bundle = generate_custom_theory_diagrams(theory_text, reaction_raw)
    terms = tuple(
        _custom_amplitude_term(theory, bundle, diagram)
        for diagram in bundle.diagrams
    )
    amplitude = CustomSymbolicAmplitude(
        reaction=bundle.reaction.raw,
        order=bundle.order,
        terms=terms,
        total_expression=_custom_total_expression(terms),
        total_annotated_expression=_custom_total_expression(terms),
        notes=(
            "Custom-theory amplitudes are unsimplified tree-level expressions built from the supplied vertex factors.",
            "They currently assume connected 2->2 diagrams composed of two 3-point vertices.",
        ),
    )
    return theory, bundle, amplitude


def parse_custom_reaction(theory: CustomTheory, raw: str) -> Reaction:
    pieces = REACTION_SPLIT_RE.split(raw.strip())
    if len(pieces) != 2:
        raise DiagramGenerationError("Reaction must contain one '->' separator.")
    left, right = pieces
    incoming = _parse_custom_side(theory, left, "incoming")
    outgoing = _parse_custom_side(theory, right, "outgoing")
    if not incoming or not outgoing:
        raise DiagramGenerationError("Reaction must have particles on both sides.")

    reaction = Reaction(raw=raw.strip(), incoming=incoming, outgoing=outgoing)
    if sum(leg.particle.charge for leg in incoming) != sum(leg.particle.charge for leg in outgoing):
        raise DiagramGenerationError("Charge is not conserved across the custom reaction.")
    return reaction


def _parse_custom_side(theory: CustomTheory, text: str, side: str) -> tuple[ExternalLeg, ...]:
    tokens = _tokenize_custom_side(tuple(theory.particles), text)
    legs = []
    for slot, token in enumerate(tokens, start=1):
        if token not in theory.particles:
            raise DiagramGenerationError(f"Unsupported custom-theory particle '{token}'.")
        legs.append(
            ExternalLeg(
                identifier=f"{'in' if side == 'incoming' else 'out'}{slot}",
                side=side,
                slot=slot,
                particle=theory.particles[token],
            )
        )
    return tuple(legs)


def _tokenize_custom_side(known_tokens: tuple[str, ...], text: str) -> list[str]:
    compact = text.strip().replace(" ", "")
    if not compact:
        return []

    ordered = sorted(known_tokens, key=len, reverse=True)
    tokens: list[str] = []
    position = 0
    while position < len(compact):
        multiplicity = 1
        if compact[position].isdigit():
            start = position
            while position < len(compact) and compact[position].isdigit():
                position += 1
            multiplicity = int(compact[start:position])
            if position < len(compact) and compact[position] == "*":
                position += 1
        for candidate in ordered:
            if compact.startswith(candidate, position):
                tokens.extend([candidate] * multiplicity)
                position += len(candidate)
                if position < len(compact):
                    if compact[position] != "+":
                        raise DiagramGenerationError(
                            f"Could not parse side '{text}'. Use '+' between particle tokens."
                        )
                    position += 1
                break
        else:
            raise DiagramGenerationError(
                f"Could not parse side '{text}' with the current custom-theory tokens."
            )
    return tokens


def _generate_tree_diagrams(theory: CustomTheory, reaction: Reaction) -> tuple[Diagram, ...]:
    legs = reaction.all_legs
    diagrams_by_key: dict[tuple, Diagram] = {}

    for partition in _pair_partitions(legs):
        group_a, group_b = partition
        matches_a = _group_vertex_matches(theory, group_a)
        matches_b = _group_vertex_matches(theory, group_b)
        for match_a in matches_a:
            for match_b in matches_b:
                connector = _connector_particle(theory, match_a[1], match_b[1])
                if connector is None:
                    continue
                normalized_partition = tuple(
                    sorted(tuple(sorted((leg.identifier for leg in group))) for group in partition)
                )
                key = (normalized_partition, connector.token, connector.kind)
                if key in diagrams_by_key:
                    continue
                channel = _classify_channel(normalized_partition)
                template = _template_for_reaction(reaction)
                topology = _topology_for_kind(connector.kind)
                title = f"{channel}-channel {connector.label} exchange" if channel else f"{connector.label} exchange"
                description = (
                    f"Vertex A uses {match_a[0].name} on {group_a[0].identifier} and {group_a[1].identifier}; "
                    f"vertex B uses {match_b[0].name} on {group_b[0].identifier} and {group_b[1].identifier}."
                )
                diagrams_by_key[key] = Diagram(
                    index=0,
                    order="tree",
                    topology=topology,
                    title=title,
                    channel=channel,
                    internal_particle=connector.token,
                    internal_momentum="q1",
                    correction=None,
                    loop_momentum=None,
                    template=template,
                    vertex_a=tuple(leg.identifier for leg in group_a),
                    vertex_b=tuple(leg.identifier for leg in group_b),
                    description=description,
                )

    diagrams = sorted(
        diagrams_by_key.values(),
        key=lambda diagram: (_channel_rank(diagram.channel), diagram.vertex_a, diagram.vertex_b),
    )
    return tuple(
        Diagram(
            index=index,
            order=diagram.order,
            topology=diagram.topology,
            title=diagram.title,
            channel=diagram.channel,
            internal_particle=diagram.internal_particle,
            internal_momentum=diagram.internal_momentum,
            correction=diagram.correction,
            loop_momentum=diagram.loop_momentum,
            template=diagram.template,
            vertex_a=diagram.vertex_a,
            vertex_b=diagram.vertex_b,
            description=diagram.description,
        )
        for index, diagram in enumerate(diagrams, start=1)
    )


def _group_vertex_matches(
    theory: CustomTheory,
    group: tuple[ExternalLeg, ExternalLeg],
) -> list[tuple[TheoryVertex, str]]:
    matches = []
    group_counter = Counter(leg.particle.token for leg in group)
    for vertex in theory.vertices:
        remaining = Counter(vertex.fields)
        if any(group_counter[token] > remaining[token] for token in group_counter):
            continue
        remaining.subtract(group_counter)
        if sum(remaining.values()) != 1:
            continue
        missing = next(token for token, count in remaining.items() if count == 1)
        matches.append((vertex, missing))
    return matches


def _connector_particle(
    theory: CustomTheory,
    token_a: str,
    token_b: str,
) -> TheoryParticle | None:
    particle_a = theory.particles[token_a]
    particle_b = theory.particles[token_b]
    if particle_a.kind != particle_b.kind:
        return None
    if particle_a.kind == "fermion":
        if particle_a.family != particle_b.family or particle_a.anti == particle_b.anti:
            return None
        return next(
            (
                particle
                for particle in theory.particles.values()
                if particle.kind == "fermion" and particle.family == particle_a.family and not particle.anti
            ),
            particle_a,
        )
    if token_a == token_b:
        return particle_a
    if particle_a.family and particle_a.family == particle_b.family and particle_a.anti != particle_b.anti:
        return particle_a
    return None


def _pair_partitions(legs: tuple[ExternalLeg, ...]) -> list[tuple[tuple[ExternalLeg, ExternalLeg], tuple[ExternalLeg, ExternalLeg]]]:
    first = legs[0]
    partitions = []
    for index in range(1, len(legs)):
        second = legs[index]
        rest = legs[1:index] + legs[index + 1 :]
        partitions.append(((first, second), (rest[0], rest[1])))
    return partitions


def _classify_channel(normalized_partition: tuple[tuple[str, str], tuple[str, str]]) -> str | None:
    pair_set = {frozenset(pair) for pair in normalized_partition}
    if pair_set == {frozenset({"in1", "in2"}), frozenset({"out1", "out2"})}:
        return "s"
    if pair_set == {frozenset({"in1", "out1"}), frozenset({"in2", "out2"})}:
        return "t"
    if pair_set == {frozenset({"in1", "out2"}), frozenset({"in2", "out1"})}:
        return "u"
    return None


def _template_for_reaction(reaction: Reaction) -> str:
    charged_in = sum(1 for leg in reaction.incoming if leg.particle.kind == "fermion")
    charged_out = sum(1 for leg in reaction.outgoing if leg.particle.kind == "fermion")
    if charged_in == 2 and charged_out == 0:
        return "fermion_annihilation"
    if charged_in == 0 and charged_out == 2:
        return "fermion_pair_production"
    if charged_in == 1 and charged_out == 1:
        return "fermion_compton"
    return "photon_horizontal"


def _topology_for_kind(kind: str) -> str:
    if kind == "fermion":
        return "fermion_exchange"
    if kind == "scalar":
        return "scalar_exchange"
    return "vector_exchange"


def _channel_rank(channel: str | None) -> int:
    ordering = {None: 9, "s": 0, "t": 1, "u": 2}
    return ordering.get(channel, 8)


def _custom_amplitude_term(
    theory: CustomTheory,
    bundle: DiagramBundle,
    diagram: Diagram,
) -> CustomAmplitudeTerm:
    term = CustomAmplitudeTerm(
        index=diagram.index,
        label=diagram.channel or str(diagram.index),
        sign=1,
        expression=_custom_diagram_expression(theory, bundle, diagram),
        annotated_expression="",
    )
    return CustomAmplitudeTerm(
        index=term.index,
        label=term.label,
        sign=term.sign,
        expression=term.expression,
        annotated_expression=term.expression,
    )


def _custom_diagram_expression(
    theory: CustomTheory,
    bundle: DiagramBundle,
    diagram: Diagram,
) -> str:
    if diagram.topology == "fermion_exchange":
        return _custom_fermion_exchange_expression(theory, bundle, diagram)
    if diagram.topology in {"scalar_exchange", "vector_exchange"}:
        return _custom_boson_exchange_expression(theory, bundle, diagram)
    raise DiagramGenerationError(f"Unsupported custom-theory topology for amplitudes: {diagram.topology}.")


def _custom_fermion_exchange_expression(
    theory: CustomTheory,
    bundle: DiagramBundle,
    diagram: Diagram,
) -> str:
    legs = {leg.identifier: leg for leg in bundle.reaction.all_legs}
    vertex_a_legs = tuple(legs[leg_id] for leg_id in diagram.vertex_a)
    vertex_b_legs = tuple(legs[leg_id] for leg_id in diagram.vertex_b)
    vertex_a = _resolve_custom_vertex(theory, diagram, vertex_a_legs)
    vertex_b = _resolve_custom_vertex(theory, diagram, vertex_b_legs)
    away = next(leg for leg in bundle.reaction.charged_legs if leg.arrow_toward_vertex is False)
    toward = next(leg for leg in bundle.reaction.charged_legs if leg.arrow_toward_vertex is True)
    away_vertex = vertex_a if away.identifier in diagram.vertex_a else vertex_b
    toward_vertex = vertex_a if toward.identifier in diagram.vertex_a else vertex_b
    q = _latex_momentum(diagram.internal_momentum)
    external_factors = " ".join(
        _custom_external_factor(leg, index)
        for leg, index in zip(
            [leg for leg in bundle.reaction.all_legs if leg.particle.kind in {"vector", "photon"}],
            [r"\alpha", r"\beta", r"\mu", r"\nu"],
        )
        if _custom_external_factor(leg, index)
    )
    chain = (
        r"\left["
        + _custom_fermion_wavefunction(away)
        + " "
        + _vertex_factor_latex(away_vertex)
        + " "
        + _custom_propagator(theory, diagram.internal_particle, q)
        + " "
        + _vertex_factor_latex(toward_vertex)
        + " "
        + _custom_fermion_wavefunction(toward)
        + r"\right]"
    )
    delta_a = _custom_vertex_delta(vertex_a_legs, diagram.internal_momentum, internal_enters=False)
    delta_b = _custom_vertex_delta(vertex_b_legs, diagram.internal_momentum, internal_enters=True)
    pieces = []
    if external_factors:
        pieces.append(external_factors)
    pieces.append(r"\int \frac{d^4 " + q + r"}{(2\pi)^4}")
    pieces.append(chain)
    pieces.append(rf"(2\pi)^4 \delta^{{(4)}}\!\left({delta_b}\right)")
    pieces.append(rf"(2\pi)^4 \delta^{{(4)}}\!\left({delta_a}\right)")
    return " ".join(pieces)


def _custom_boson_exchange_expression(
    theory: CustomTheory,
    bundle: DiagramBundle,
    diagram: Diagram,
) -> str:
    legs = {leg.identifier: leg for leg in bundle.reaction.all_legs}
    vertex_a_legs = tuple(legs[leg_id] for leg_id in diagram.vertex_a)
    vertex_b_legs = tuple(legs[leg_id] for leg_id in diagram.vertex_b)
    vertex_a = _resolve_custom_vertex(theory, diagram, vertex_a_legs)
    vertex_b = _resolve_custom_vertex(theory, diagram, vertex_b_legs)
    q = _latex_momentum(diagram.internal_momentum)
    left = _custom_vertex_external_product(vertex_a_legs, vertex_a)
    right = _custom_vertex_external_product(vertex_b_legs, vertex_b)
    delta_a = _custom_vertex_delta(vertex_a_legs, diagram.internal_momentum, internal_enters=False)
    delta_b = _custom_vertex_delta(vertex_b_legs, diagram.internal_momentum, internal_enters=True)
    return " ".join(
        [
            r"\int \frac{d^4 " + q + r"}{(2\pi)^4}",
            left,
            _custom_propagator(theory, diagram.internal_particle, q),
            right,
            rf"(2\pi)^4 \delta^{{(4)}}\!\left({delta_b}\right)",
            rf"(2\pi)^4 \delta^{{(4)}}\!\left({delta_a}\right)",
        ]
    )


def _resolve_custom_vertex(
    theory: CustomTheory,
    diagram: Diagram,
    group: tuple[ExternalLeg, ExternalLeg],
) -> TheoryVertex:
    matches = _group_vertex_matches(theory, group)
    internal_particle = theory.particles[diagram.internal_particle]
    for vertex, missing in matches:
        missing_particle = theory.particles[missing]
        if missing_particle.kind != internal_particle.kind:
            continue
        if missing_particle.kind == "fermion":
            if missing_particle.family == internal_particle.family:
                return vertex
            continue
        if missing_particle.token == internal_particle.token:
            return vertex
    raise DiagramGenerationError("Could not resolve the matching custom vertex for a generated diagram.")


def _custom_vertex_external_product(
    group: tuple[ExternalLeg, ExternalLeg],
    vertex: TheoryVertex,
) -> str:
    factors = [_custom_external_factor(leg, r"\mu" if position == 0 else r"\nu") for position, leg in enumerate(group)]
    factors = [factor for factor in factors if factor]
    factor = _vertex_factor_latex(vertex)
    if factors:
        return r"\left[" + " ".join(factors + [factor]) + r"\right]"
    return r"\left[" + factor + r"\right]"


def _custom_external_factor(leg: ExternalLeg, index: str) -> str:
    if leg.particle.kind == "fermion":
        return _custom_fermion_wavefunction(leg)
    if leg.particle.kind in {"vector", "photon"}:
        momentum = _latex_momentum(leg.momentum_label)
        if leg.side == "incoming":
            return rf"\varepsilon_{{{index}}}\!\left({momentum}\right)"
        return rf"\varepsilon_{{{index}}}^{{*}}\!\left({momentum}\right)"
    return ""


def _custom_fermion_wavefunction(leg: ExternalLeg) -> str:
    spin = f"i_{{{leg.slot}}}" + ("'" if leg.side == "outgoing" else "")
    momentum = _latex_momentum(leg.momentum_label)
    if not leg.particle.anti and leg.side == "incoming":
        return rf"u^{{({spin})}}\!\left({momentum}\right)"
    if not leg.particle.anti and leg.side == "outgoing":
        return rf"\bar{{u}}^{{({spin})}}\!\left({momentum}\right)"
    if leg.particle.anti and leg.side == "incoming":
        return rf"\bar{{v}}^{{({spin})}}\!\left({momentum}\right)"
    return rf"v^{{({spin})}}\!\left({momentum}\right)"


def _vertex_factor_latex(vertex: TheoryVertex) -> str:
    return vertex.factor or rf"g_{{{vertex.name}}}"


def _custom_propagator(theory: CustomTheory, token: str, q: str) -> str:
    particle = theory.particles[token]
    mass = _custom_mass_symbol(particle)
    if particle.kind == "fermion":
        return rf"\left(\frac{{i (\gamma \cdot {q} + {mass})}}{{{q}^2 - {mass}^2}}\right)"
    if particle.kind == "scalar":
        if mass == "0":
            return rf"\left(\frac{{i}}{{{q}^2}}\right)"
        return rf"\left(\frac{{i}}{{{q}^2 - {mass}^2}}\right)"
    if mass == "0":
        return rf"\left(\frac{{-i g_{{\mu \nu}}}}{{{q}^2}}\right)"
    return rf"\left(\frac{{-i g_{{\mu \nu}}}}{{{q}^2 - {mass}^2}}\right)"


def _custom_mass_symbol(particle: TheoryParticle) -> str:
    if particle.mass_symbol:
        return particle.mass_symbol
    return "m_" + particle.token.replace("+", "plus").replace("-", "minus")


def _custom_vertex_delta(
    group: tuple[ExternalLeg, ExternalLeg],
    internal_momentum: str,
    *,
    internal_enters: bool,
) -> str:
    terms = []
    for leg in group:
        sign = "+" if leg.side == "incoming" else "-"
        terms.append((sign, _latex_momentum(leg.momentum_label)))
    terms.append(("+" if internal_enters else "-", _latex_momentum(internal_momentum)))
    return _format_signed_terms(terms)


def _format_signed_terms(terms: list[tuple[str, str]]) -> str:
    pieces = []
    for position, (sign, term) in enumerate(terms):
        if position == 0:
            pieces.append(term if sign == "+" else f"- {term}")
            continue
        pieces.append(f"{sign} {term}")
    return " ".join(pieces)


def _custom_total_expression(terms: tuple[CustomAmplitudeTerm, ...]) -> str:
    pieces = [r"-i \mathcal{M} = "]
    for position, term in enumerate(terms):
        piece = rf"\left(-i \mathcal{{M}}_{{{term.label}}}\right)"
        if position == 0:
            pieces.append(piece)
        else:
            pieces.append(" + " + piece if term.sign > 0 else " - " + piece)
    return "".join(pieces)


def _latex_momentum(label: str) -> str:
    if label.startswith("p") and label.endswith("'"):
        return rf"p_{{{label[1:-1]}}}'"
    if label.startswith("p"):
        return rf"p_{{{label[1:]}}}"
    if label.startswith("q"):
        return rf"q_{{{label[1:]}}}"
    return label
