from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Particle:
    token: str
    label: str
    kind: str
    family: str | None
    charge: int
    anti: bool = False


PARTICLES = {
    "e-": Particle("e-", "e-", "fermion", "electron", -1, False),
    "e+": Particle("e+", "e+", "fermion", "electron", 1, True),
    "mu-": Particle("mu-", "mu-", "fermion", "muon", -1, False),
    "mu+": Particle("mu+", "mu+", "fermion", "muon", 1, True),
    "tau-": Particle("tau-", "tau-", "fermion", "tau", -1, False),
    "tau+": Particle("tau+", "tau+", "fermion", "tau", 1, True),
    "gamma": Particle("gamma", "gamma", "photon", None, 0, False),
}

ALIASES = {
    "electron": "e-",
    "positron": "e+",
    "muon": "mu-",
    "antimuon": "mu+",
    "tau": "tau-",
    "antitau": "tau+",
    "photon": "gamma",
    "a": "gamma",
}

REACTION_SPLIT_RE = re.compile(r"\s*(?:->|=>)\s*")


class DiagramGenerationError(ValueError):
    """Raised when a reaction cannot be represented by this generator."""


@dataclass(frozen=True)
class ExternalLeg:
    identifier: str
    side: str
    slot: int
    particle: Particle

    @property
    def order_key(self) -> tuple[int, int]:
        return (0 if self.side == "incoming" else 1, self.slot)

    @property
    def arrow_toward_vertex(self) -> bool | None:
        if self.particle.kind != "fermion":
            return None
        return (self.side == "incoming") != self.particle.anti

    @property
    def momentum_label(self) -> str:
        return f"p{self.slot}" if self.side == "incoming" else f"p{self.slot}'"


@dataclass(frozen=True)
class Reaction:
    raw: str
    incoming: tuple[ExternalLeg, ...]
    outgoing: tuple[ExternalLeg, ...]

    @property
    def all_legs(self) -> tuple[ExternalLeg, ...]:
        return self.incoming + self.outgoing

    @property
    def charged_legs(self) -> tuple[ExternalLeg, ...]:
        return tuple(leg for leg in self.all_legs if leg.particle.kind == "fermion")

    @property
    def photon_legs(self) -> tuple[ExternalLeg, ...]:
        return tuple(leg for leg in self.all_legs if leg.particle.kind == "photon")


@dataclass(frozen=True)
class Diagram:
    index: int
    order: str
    topology: str
    title: str
    channel: str | None
    internal_particle: str
    internal_momentum: str
    correction: str | None
    loop_momentum: str | None
    template: str
    vertex_a: tuple[str, ...]
    vertex_b: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class DiagramBundle:
    reaction: Reaction
    order: str
    diagrams: tuple[Diagram, ...]
    notes: tuple[str, ...]


def parse_reaction(raw: str) -> Reaction:
    pieces = REACTION_SPLIT_RE.split(raw.strip())
    if len(pieces) != 2:
        raise DiagramGenerationError("Reaction must contain one '->' separator.")

    left, right = pieces
    incoming = _parse_side(left, "incoming")
    outgoing = _parse_side(right, "outgoing")

    if not incoming or not outgoing:
        raise DiagramGenerationError("Reaction must have particles on both sides.")

    reaction = Reaction(raw=raw.strip(), incoming=incoming, outgoing=outgoing)
    _validate_reaction(reaction)
    return reaction


def generate_diagrams(raw: str, order: str = "tree") -> DiagramBundle:
    reaction = parse_reaction(raw)
    order_name = _normalize_order(order)

    if len(reaction.incoming) != 2 or len(reaction.outgoing) != 2:
        raise DiagramGenerationError(
            "This first implementation supports lowest-order 2->2 QED reactions only."
        )

    charged = reaction.charged_legs
    photons = reaction.photon_legs

    if len(charged) == 4:
        diagrams = _generate_photon_exchange_diagrams(reaction, charged)
    elif len(charged) == 2 and len(photons) == 2:
        diagrams = _generate_fermion_exchange_diagrams(reaction, charged, photons)
    else:
        diagrams = ()

    if not diagrams:
        raise DiagramGenerationError(
            "No connected lowest-order tree-level QED diagrams exist for this 2->2 reaction."
        )

    if order_name == "one-loop":
        diagrams = _decorate_one_loop_diagrams(reaction, diagrams)

    notes = _build_notes(reaction, diagrams, order_name)
    return DiagramBundle(reaction=reaction, order=order_name, diagrams=diagrams, notes=notes)


def _parse_side(text: str, side: str) -> tuple[ExternalLeg, ...]:
    tokens = _tokenize_side(text)

    legs = []
    for slot, token in enumerate(tokens, start=1):
        normalized = _normalize_token(token)
        if normalized not in PARTICLES:
            allowed = ", ".join(sorted(PARTICLES))
            raise DiagramGenerationError(
                f"Unsupported particle '{token}'. Supported tokens: {allowed}."
            )
        legs.append(
            ExternalLeg(
                identifier=f"{'in' if side == 'incoming' else 'out'}{slot}",
                side=side,
                slot=slot,
                particle=PARTICLES[normalized],
            )
        )
    return tuple(legs)


def _normalize_token(token: str) -> str:
    compact = token.strip().lower().replace(" ", "")
    return ALIASES.get(compact, compact)


def _tokenize_side(text: str) -> list[str]:
    compact = text.strip().lower().replace(" ", "")
    if not compact:
        return []

    known_tokens = sorted(
        set(PARTICLES) | set(ALIASES),
        key=len,
        reverse=True,
    )

    tokens = []
    position = 0
    while position < len(compact):
        for candidate in known_tokens:
            if compact.startswith(candidate, position):
                tokens.append(candidate)
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
                f"Could not parse side '{text}'. Use supported particle tokens such as e-, e+, mu-, mu+, gamma."
            )

    return tokens


def _validate_reaction(reaction: Reaction) -> None:
    incoming_charge = sum(leg.particle.charge for leg in reaction.incoming)
    outgoing_charge = sum(leg.particle.charge for leg in reaction.outgoing)
    if incoming_charge != outgoing_charge:
        raise DiagramGenerationError("Charge is not conserved across the reaction.")

    families = {leg.particle.family for leg in reaction.charged_legs}
    if None in families:
        families.remove(None)
    if len(families) > 3:
        raise DiagramGenerationError("Only electron, muon, and tau external fermions are supported.")


def _generate_photon_exchange_diagrams(
    reaction: Reaction, charged: tuple[ExternalLeg, ...]
) -> tuple[Diagram, ...]:
    valid_partitions: dict[tuple[tuple[str, str], tuple[str, str]], Diagram] = {}

    for partition in _pair_partitions(charged):
        if not all(_is_valid_photon_vertex(pair) for pair in partition):
            continue

        normalized_partition = tuple(
            sorted(tuple(sorted((pair[0].identifier, pair[1].identifier))) for pair in partition)
        )
        if normalized_partition in valid_partitions:
            continue

        channel = _classify_photon_channel(normalized_partition)
        vertex_a, vertex_b, template = _order_photon_vertices(partition, channel)
        title = f"{channel}-channel photon exchange" if channel else "photon exchange"
        description = _describe_vertex_partition(vertex_a, vertex_b, "virtual photon")

        valid_partitions[normalized_partition] = Diagram(
            index=0,
            order="tree",
            topology="photon_exchange",
            title=title,
            channel=channel,
            internal_particle="gamma",
            internal_momentum="q1",
            correction=None,
            loop_momentum=None,
            template=template,
            vertex_a=tuple(leg.identifier for leg in vertex_a),
            vertex_b=tuple(leg.identifier for leg in vertex_b),
            description=description,
        )

    diagrams = sorted(
        valid_partitions.values(),
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


def _generate_fermion_exchange_diagrams(
    reaction: Reaction,
    charged: tuple[ExternalLeg, ...],
    photons: tuple[ExternalLeg, ...],
) -> tuple[Diagram, ...]:
    if charged[0].particle.family != charged[1].particle.family:
        raise DiagramGenerationError(
            "Lowest-order fermion-exchange diagrams require the charged external legs "
            "to belong to the same fermion family."
        )

    arrows = {leg.arrow_toward_vertex for leg in charged}
    if arrows != {True, False}:
        raise DiagramGenerationError(
            "The charged external legs cannot be connected into a single QED fermion line "
            "at lowest order."
        )

    start_charge = next(leg for leg in charged if leg.arrow_toward_vertex)
    end_charge = next(leg for leg in charged if not leg.arrow_toward_vertex)
    photon_orders = [
        (photons[0], photons[1]),
        (photons[1], photons[0]),
    ]
    template = _fermion_template(reaction)

    diagrams = []
    for index, (start_photon, end_photon) in enumerate(photon_orders, start=1):
        channel = _classify_fermion_channel(reaction, start_photon)
        title = f"{channel}-channel fermion exchange" if channel else "fermion exchange"
        description = (
            f"Vertex A joins {start_charge.identifier} and {start_photon.identifier}; "
            f"vertex B joins {end_charge.identifier} and {end_photon.identifier} "
            f"through a virtual {start_charge.particle.family} line."
        )
        diagrams.append(
            Diagram(
                index=index,
                order="tree",
                topology="fermion_exchange",
                title=title,
                channel=channel,
                internal_particle=start_charge.particle.token,
                internal_momentum="q1",
                correction=None,
                loop_momentum=None,
                template=template,
                vertex_a=(start_charge.identifier, start_photon.identifier),
                vertex_b=(end_charge.identifier, end_photon.identifier),
                description=description,
            )
        )

    diagrams.sort(key=lambda diagram: (_channel_rank(diagram.channel), diagram.vertex_a, diagram.vertex_b))
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


def _pair_partitions(legs: tuple[ExternalLeg, ...]) -> list[tuple[tuple[ExternalLeg, ExternalLeg], ...]]:
    if not legs:
        return [()]

    first = legs[0]
    partitions = []
    for index in range(1, len(legs)):
        second = legs[index]
        rest = legs[1:index] + legs[index + 1 :]
        for suffix in _pair_partitions(rest):
            partitions.append(((first, second),) + suffix)
    return partitions


def _is_valid_photon_vertex(pair: tuple[ExternalLeg, ExternalLeg]) -> bool:
    left, right = pair
    return (
        left.particle.kind == "fermion"
        and right.particle.kind == "fermion"
        and left.particle.family == right.particle.family
        and left.arrow_toward_vertex != right.arrow_toward_vertex
    )


def _classify_photon_channel(
    normalized_partition: tuple[tuple[str, str], tuple[str, str]]
) -> str | None:
    pair_set = {frozenset(pair) for pair in normalized_partition}
    if pair_set == {frozenset({"in1", "in2"}), frozenset({"out1", "out2"})}:
        return "s"
    if pair_set == {frozenset({"in1", "out1"}), frozenset({"in2", "out2"})}:
        return "t"
    if pair_set == {frozenset({"in1", "out2"}), frozenset({"in2", "out1"})}:
        return "u"
    return None


def _order_photon_vertices(
    partition: tuple[tuple[ExternalLeg, ExternalLeg], ...], channel: str | None
) -> tuple[tuple[ExternalLeg, ExternalLeg], tuple[ExternalLeg, ExternalLeg], str]:
    if channel == "s":
        lower = next(pair for pair in partition if all(leg.side == "incoming" for leg in pair))
        upper = next(pair for pair in partition if all(leg.side == "outgoing" for leg in pair))
        return lower, upper, "photon_vertical"

    ordered_pairs = sorted(
        partition,
        key=lambda pair: min(
            0 if leg.identifier == "in1" else 1 if leg.identifier == "in2" else 2 if leg.identifier == "out1" else 3
            for leg in pair
        ),
    )
    return ordered_pairs[0], ordered_pairs[1], "photon_horizontal"


def _fermion_template(reaction: Reaction) -> str:
    charged_in = sum(1 for leg in reaction.incoming if leg.particle.kind == "fermion")
    charged_out = sum(1 for leg in reaction.outgoing if leg.particle.kind == "fermion")

    if charged_in == 1 and charged_out == 1:
        return "fermion_compton"
    if charged_in == 2:
        return "fermion_annihilation"
    return "fermion_pair_production"


def _classify_fermion_channel(reaction: Reaction, start_photon: ExternalLeg) -> str | None:
    photon_in = [leg for leg in reaction.incoming if leg.particle.kind == "photon"]
    photon_out = [leg for leg in reaction.outgoing if leg.particle.kind == "photon"]

    if len(photon_in) == 1 and len(photon_out) == 1:
        return "s" if start_photon.side == "incoming" else "u"

    if len(photon_in) == 2 or len(photon_out) == 2:
        return "t" if start_photon.slot == 1 else "u"

    return None


def _describe_vertex_partition(
    vertex_a: tuple[ExternalLeg, ExternalLeg],
    vertex_b: tuple[ExternalLeg, ExternalLeg],
    internal_name: str,
) -> str:
    return (
        f"Vertex A joins {vertex_a[0].identifier} and {vertex_a[1].identifier}; "
        f"vertex B joins {vertex_b[0].identifier} and {vertex_b[1].identifier} "
        f"through a {internal_name}."
    )


def _build_notes(
    reaction: Reaction,
    diagrams: tuple[Diagram, ...],
    order: str,
) -> tuple[str, ...]:
    notes = [
        "This tool follows the QED vertex rule: every vertex has exactly one photon line and two fermion legs.",
    ]
    if order == "tree":
        notes.append("Only topologically inequivalent connected tree diagrams at lowest non-zero order are drawn.")
    else:
        notes.append(
            "One-loop mode currently draws vacuum-polarization corrections on virtual-photon exchange diagrams."
        )

    charged_families = [leg.particle.family for leg in reaction.charged_legs]
    if (
        len(reaction.charged_legs) == 4
        and len(diagrams) > 1
        and charged_families
        and len(set(charged_families)) == 1
    ):
        notes.append(
            "Multiple diagrams are related by identical-fermion interchange; relative minus signs matter in amplitudes, "
            "but this tool intentionally stops at topology and drawing."
        )

    return tuple(notes)


def _normalize_order(order: str) -> str:
    normalized = order.strip().lower().replace("_", "-")
    aliases = {
        "tree": "tree",
        "lowest": "tree",
        "lowest-order": "tree",
        "one-loop": "one-loop",
        "loop": "one-loop",
    }
    if normalized not in aliases:
        raise DiagramGenerationError("Supported orders are 'tree' and 'one-loop'.")
    return aliases[normalized]


def _decorate_one_loop_diagrams(
    reaction: Reaction,
    diagrams: tuple[Diagram, ...],
) -> tuple[Diagram, ...]:
    if not diagrams or not all(diagram.topology == "photon_exchange" for diagram in diagrams):
        raise DiagramGenerationError(
            "One-loop mode currently supports four-fermion reactions with virtual-photon exchange only."
        )

    if reaction.photon_legs:
        raise DiagramGenerationError(
            "One-loop mode is currently limited to reactions without external photons."
        )

    return tuple(
        Diagram(
            index=index,
            order="one-loop",
            topology=diagram.topology,
            title=f"{diagram.title} with vacuum polarization",
            channel=diagram.channel,
            internal_particle=diagram.internal_particle,
            internal_momentum=diagram.internal_momentum,
            correction="vacuum_polarization",
            loop_momentum="ell1",
            template=diagram.template,
            vertex_a=diagram.vertex_a,
            vertex_b=diagram.vertex_b,
            description=(
                f"{diagram.description[:-1]} with a one-loop fermion bubble inserted on the "
                f"virtual photon propagator."
            ),
        )
        for index, diagram in enumerate(diagrams, start=1)
    )


def _channel_rank(channel: str | None) -> int:
    ordering = {None: 9, "s": 0, "t": 1, "u": 2}
    return ordering.get(channel, 8)


def diagram_lookup(diagram_bundle: DiagramBundle) -> dict[str, ExternalLeg]:
    return {leg.identifier: leg for leg in diagram_bundle.reaction.all_legs}
