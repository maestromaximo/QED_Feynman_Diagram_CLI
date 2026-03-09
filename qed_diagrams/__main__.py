from __future__ import annotations

import argparse
from pathlib import Path

from .core import DiagramGenerationError, generate_diagrams
from .render import RenderOptions, render_diagram_svg
from .web import serve


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lowest-order QED Feynman diagram editor and generator."
    )
    subparsers = parser.add_subparsers(dest="command")

    render_parser = subparsers.add_parser("render", help="Generate SVG files for one reaction.")
    render_parser.add_argument("reaction", help="Reaction string, for example: e- + e+ -> mu- + mu+")
    render_parser.add_argument(
        "--output-dir",
        default="generated_diagrams",
        help="Directory where SVG files will be written.",
    )
    render_parser.add_argument(
        "--order",
        default="tree",
        choices=["tree", "one-loop"],
        help="Perturbative order to draw.",
    )
    render_parser.add_argument(
        "--compact",
        action="store_true",
        help="Use a more compact diagram layout.",
    )
    render_parser.add_argument(
        "--show-leg-ids",
        action="store_true",
        help="Show leg identifiers such as in1/out2 next to labels.",
    )
    render_parser.add_argument(
        "--hide-momenta",
        action="store_true",
        help="Hide momentum labels such as p1, p1', and q1.",
    )

    serve_parser = subparsers.add_parser("serve", help="Run the local browser UI.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    if args.command == "serve":
        serve(args.host, args.port)
        return 0

    if args.command == "render":
        try:
            bundle = generate_diagrams(args.reaction, order=args.order)
        except DiagramGenerationError as exc:
            parser.error(str(exc))

        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        options = RenderOptions(
            compact=args.compact,
            show_leg_ids=args.show_leg_ids,
            show_momenta=not args.hide_momenta,
        )

        for diagram in bundle.diagrams:
            svg = render_diagram_svg(bundle, diagram, options)
            filename = f"diagram-{diagram.index:02d}-{diagram.title.replace(' ', '-').lower()}.svg"
            path = output_dir / filename
            path.write_text(svg, encoding="utf-8")
            print(path)

        for note in bundle.notes:
            print(f"note: {note}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
