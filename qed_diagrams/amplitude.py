from __future__ import annotations

from dataclasses import dataclass

from .core import Diagram, DiagramBundle, DiagramGenerationError, ExternalLeg, generate_diagrams


@dataclass(frozen=True)
class AmplitudeTerm:
    index: int
    label: str
    sign: int
    expression: str
    annotated_expression: str


@dataclass(frozen=True)
class SymbolicAmplitude:
    reaction: str
    order: str
    terms: tuple[AmplitudeTerm, ...]
    total_expression: str
    total_annotated_expression: str
    notes: tuple[str, ...]


def generate_symbolic_amplitudes(raw: str, order: str = "tree") -> SymbolicAmplitude:
    bundle = generate_diagrams(raw, order=order)
    if bundle.order != "tree":
        raise DiagramGenerationError(
            "Rule-based symbolic amplitudes are currently implemented for leading-order tree diagrams only."
        )

    signs = _diagram_signs(bundle)
    terms = tuple(
        AmplitudeTerm(
            index=diagram.index,
            label=_diagram_label(diagram),
            sign=signs[position],
            expression=_diagram_expression(bundle, diagram),
            annotated_expression=_diagram_annotated_expression(bundle, diagram),
        )
        for position, diagram in enumerate(bundle.diagrams)
    )
    return SymbolicAmplitude(
        reaction=bundle.reaction.raw,
        order=bundle.order,
        terms=terms,
        total_expression=_total_expression(terms),
        total_annotated_expression=_total_expression(terms),
        notes=(
            "Expressions are unsimplified rule-based tree-level amplitudes.",
            "Each term keeps the internal momentum integral and one momentum-conservation delta function per vertex.",
        ),
    )


def _diagram_signs(bundle: DiagramBundle) -> list[int]:
    signs = [1] * len(bundle.diagrams)
    if (
        len(bundle.diagrams) > 1
        and all(diagram.topology == "photon_exchange" for diagram in bundle.diagrams)
    ):
        families = [leg.particle.family for leg in bundle.reaction.charged_legs if leg.particle.family]
        if families and len(set(families)) == 1:
            for index in range(1, len(signs)):
                signs[index] = -1
    return signs


def _diagram_label(diagram: Diagram) -> str:
    return diagram.channel or f"{diagram.index}"


def _diagram_expression(bundle: DiagramBundle, diagram: Diagram) -> str:
    if diagram.topology == "photon_exchange":
        return _photon_exchange_expression(bundle, diagram)
    if diagram.topology == "fermion_exchange":
        return _fermion_exchange_expression(bundle, diagram)
    raise DiagramGenerationError(f"Unsupported topology for symbolic amplitude: {diagram.topology}.")


def _diagram_annotated_expression(bundle: DiagramBundle, diagram: Diagram) -> str:
    if diagram.topology == "photon_exchange":
        return _annotated_photon_exchange_expression(bundle, diagram)
    if diagram.topology == "fermion_exchange":
        return _annotated_fermion_exchange_expression(bundle, diagram)
    raise DiagramGenerationError(f"Unsupported topology for symbolic amplitude: {diagram.topology}.")


def _photon_exchange_expression(bundle: DiagramBundle, diagram: Diagram) -> str:
    legs = {leg.identifier: leg for leg in bundle.reaction.all_legs}
    vertex_a = tuple(legs[leg_id] for leg_id in diagram.vertex_a)
    vertex_b = tuple(legs[leg_id] for leg_id in diagram.vertex_b)
    mu = r"\mu"
    nu = r"\nu"
    current_a = _fermion_vertex_factor(vertex_a, mu)
    current_b = _fermion_vertex_factor(vertex_b, nu)
    delta_a = _vertex_delta(vertex_a, diagram.internal_momentum, internal_enters=False)
    delta_b = _vertex_delta(vertex_b, diagram.internal_momentum, internal_enters=True)
    q = _latex_momentum(diagram.internal_momentum)
    return (
        r"\int \frac{d^4 " + q + r"}{(2\pi)^4} "
        + r"\left[" + current_a + r"\right] "
        + rf"\left(\frac{{-i g_{{{mu} {nu}}}}}{{{q}^2}}\right) "
        + r"\left[" + current_b + r"\right] "
        + rf"(2\pi)^4 \delta^{{(4)}}\!\left({delta_b}\right) "
        + rf"(2\pi)^4 \delta^{{(4)}}\!\left({delta_a}\right)"
    )


def _fermion_exchange_expression(bundle: DiagramBundle, diagram: Diagram) -> str:
    legs = {leg.identifier: leg for leg in bundle.reaction.all_legs}
    vertex_a = tuple(legs[leg_id] for leg_id in diagram.vertex_a)
    vertex_b = tuple(legs[leg_id] for leg_id in diagram.vertex_b)
    alpha = r"\alpha"
    beta = r"\beta"
    photon_a = next(leg for leg in vertex_a if leg.particle.kind == "photon")
    photon_b = next(leg for leg in vertex_b if leg.particle.kind == "photon")
    toward = next(leg for leg in bundle.reaction.charged_legs if leg.arrow_toward_vertex)
    away = next(leg for leg in bundle.reaction.charged_legs if not leg.arrow_toward_vertex)
    q = _latex_momentum(diagram.internal_momentum)
    propagator = _fermion_propagator(diagram.internal_particle, q)
    polarization_factors = " ".join(
        _photon_factor(leg, alpha if leg.identifier == photon_a.identifier else beta)
        for leg in bundle.reaction.all_legs
        if leg.particle.kind == "photon"
    )
    chain = (
        r"\left["
        + _fermion_wavefunction(away)
        + rf" (-i e \gamma^{{{beta}}}) "
        + propagator
        + rf" (-i e \gamma^{{{alpha}}}) "
        + _fermion_wavefunction(toward)
        + r"\right]"
    )
    delta_a = _vertex_delta(vertex_a, diagram.internal_momentum, internal_enters=False)
    delta_b = _vertex_delta(vertex_b, diagram.internal_momentum, internal_enters=True)
    factors = []
    if polarization_factors:
        factors.append(polarization_factors)
    factors.append(r"\int \frac{d^4 " + q + r"}{(2\pi)^4}")
    factors.append(chain)
    factors.append(rf"(2\pi)^4 \delta^{{(4)}}\!\left({delta_b}\right)")
    factors.append(rf"(2\pi)^4 \delta^{{(4)}}\!\left({delta_a}\right)")
    return " ".join(factors)


def _annotated_photon_exchange_expression(bundle: DiagramBundle, diagram: Diagram) -> str:
    legs = {leg.identifier: leg for leg in bundle.reaction.all_legs}
    vertex_a = tuple(legs[leg_id] for leg_id in diagram.vertex_a)
    vertex_b = tuple(legs[leg_id] for leg_id in diagram.vertex_b)
    mu = r"\mu"
    nu = r"\nu"
    q = _latex_momentum(diagram.internal_momentum)
    delta_a = _vertex_delta(vertex_a, diagram.internal_momentum, internal_enters=False)
    delta_b = _vertex_delta(vertex_b, diagram.internal_momentum, internal_enters=True)
    return " ".join(
        [
            _annotate(r"\int \frac{d^4 " + q + r"}{(2\pi)^4}", 5),
            _annotated_fermion_vertex_factor(vertex_a, mu),
            _annotate(rf"\left(\frac{{-i g_{{{mu} {nu}}}}}{{{q}^2}}\right)", 3),
            _annotated_fermion_vertex_factor(vertex_b, nu),
            _annotate(
                rf"(2\pi)^4 \delta^{{(4)}}\!\left({delta_b}\right) "
                rf"(2\pi)^4 \delta^{{(4)}}\!\left({delta_a}\right)",
                4,
            ),
        ]
    )


def _annotated_fermion_exchange_expression(bundle: DiagramBundle, diagram: Diagram) -> str:
    legs = {leg.identifier: leg for leg in bundle.reaction.all_legs}
    vertex_a = tuple(legs[leg_id] for leg_id in diagram.vertex_a)
    vertex_b = tuple(legs[leg_id] for leg_id in diagram.vertex_b)
    alpha = r"\alpha"
    beta = r"\beta"
    photon_a = next(leg for leg in vertex_a if leg.particle.kind == "photon")
    photon_b = next(leg for leg in vertex_b if leg.particle.kind == "photon")
    toward = next(leg for leg in bundle.reaction.charged_legs if leg.arrow_toward_vertex)
    away = next(leg for leg in bundle.reaction.charged_legs if not leg.arrow_toward_vertex)
    q = _latex_momentum(diagram.internal_momentum)
    delta_a = _vertex_delta(vertex_a, diagram.internal_momentum, internal_enters=False)
    delta_b = _vertex_delta(vertex_b, diagram.internal_momentum, internal_enters=True)
    polarization_factors = " ".join(
        _annotate(
            _photon_factor(leg, alpha if leg.identifier == photon_a.identifier else beta),
            2,
        )
        for leg in bundle.reaction.all_legs
        if leg.particle.kind == "photon"
    )
    chain = (
        r"\left["
        + _annotate(_fermion_wavefunction(away), 2)
        + " "
        + _annotate(rf"(-i e \gamma^{{{beta}}})", 6)
        + " "
        + _annotate(_fermion_propagator(diagram.internal_particle, q), 3)
        + " "
        + _annotate(rf"(-i e \gamma^{{{alpha}}})", 6)
        + " "
        + _annotate(_fermion_wavefunction(toward), 2)
        + r"\right]"
    )
    return " ".join(
        [
            polarization_factors,
            _annotate(r"\int \frac{d^4 " + q + r"}{(2\pi)^4}", 5),
            chain,
            _annotate(
                rf"(2\pi)^4 \delta^{{(4)}}\!\left({delta_b}\right) "
                rf"(2\pi)^4 \delta^{{(4)}}\!\left({delta_a}\right)",
                4,
            ),
        ]
    ).strip()


def _fermion_vertex_factor(vertex: tuple[ExternalLeg, ExternalLeg], index: str) -> str:
    away = next(leg for leg in vertex if leg.arrow_toward_vertex is False)
    toward = next(leg for leg in vertex if leg.arrow_toward_vertex is True)
    return (
        _fermion_wavefunction(away)
        + rf" (-i e \gamma^{{{index}}}) "
        + _fermion_wavefunction(toward)
    )


def _annotated_fermion_vertex_factor(vertex: tuple[ExternalLeg, ExternalLeg], index: str) -> str:
    away = next(leg for leg in vertex if leg.arrow_toward_vertex is False)
    toward = next(leg for leg in vertex if leg.arrow_toward_vertex is True)
    return (
        r"\left["
        + _annotate(_fermion_wavefunction(away), 2)
        + " "
        + _annotate(rf"(-i e \gamma^{{{index}}})", 6)
        + " "
        + _annotate(_fermion_wavefunction(toward), 2)
        + r"\right]"
    )


def _fermion_wavefunction(leg: ExternalLeg) -> str:
    spin = f"i_{{{leg.slot}}}" + ("'" if leg.side == "outgoing" else "")
    momentum = _latex_momentum(leg.momentum_label)
    if not leg.particle.anti and leg.side == "incoming":
        return rf"u^{{({spin})}}\!\left({momentum}\right)"
    if not leg.particle.anti and leg.side == "outgoing":
        return rf"\bar{{u}}^{{({spin})}}\!\left({momentum}\right)"
    if leg.particle.anti and leg.side == "incoming":
        return rf"\bar{{v}}^{{({spin})}}\!\left({momentum}\right)"
    return rf"v^{{({spin})}}\!\left({momentum}\right)"


def _photon_factor(leg: ExternalLeg, index: str) -> str:
    momentum = _latex_momentum(leg.momentum_label)
    if leg.side == "incoming":
        return rf"\varepsilon_{{{index}}}\!\left({momentum}\right)"
    return rf"\varepsilon_{{{index}}}^{{*}}\!\left({momentum}\right)"


def _fermion_propagator(particle_token: str, q: str) -> str:
    mass = _mass_symbol(particle_token)
    return rf"\left(\frac{{i (\gamma \cdot {q} + {mass})}}{{{q}^2 - {mass}^2}}\right)"


def _mass_symbol(particle_token: str) -> str:
    family = particle_token.replace("+", "-")
    mapping = {
        "e-": "m_e",
        "mu-": "m_mu",
        "tau-": "m_tau",
    }
    return mapping.get(family, "m")


def _vertex_delta(
    vertex: tuple[ExternalLeg, ...],
    internal_momentum: str,
    *,
    internal_enters: bool,
) -> str:
    terms = []
    for leg in vertex:
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


def _total_expression(terms: tuple[AmplitudeTerm, ...]) -> str:
    pieces = [r"-i \mathcal{M} = "]
    for position, term in enumerate(terms):
        signed_term = rf"\left(-i \mathcal{{M}}_{{{term.label}}}\right)"
        if position == 0:
            pieces.append(signed_term if term.sign > 0 else "- " + signed_term)
            continue
        pieces.append(" + " + signed_term if term.sign > 0 else " - " + signed_term)
    return "".join(pieces)


def _annotate(expression: str, rule_number: int) -> str:
    return rf"\underbrace{{{expression}}}_{{\text{{rule {rule_number}}}}}"


def _latex_momentum(label: str) -> str:
    if label.startswith("p") and label.endswith("'"):
        return rf"p_{{{label[1:-1]}}}'"
    if label.startswith("p"):
        return rf"p_{{{label[1:]}}}"
    if label.startswith("q"):
        return rf"q_{{{label[1:]}}}"
    if label.startswith("ell"):
        return rf"\ell_{{{label[3:]}}}"
    return label
