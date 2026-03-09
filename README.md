# QED Diagram Editor

This repository now contains a working QED Feynman diagram editor/generator with:

- roomy SVG layouts,
- a browser carousel for cycling through generated diagrams,
- explicit momentum labels on external and internal lines,
- tree-level generation for supported `2 -> 2` reactions,
- initial one-loop support for vacuum-polarization corrections on virtual-photon exchange diagrams.

It does one job deliberately:

- parse a `2 -> 2` reaction,
- enforce the basic QED vertex/topology rules,
- enumerate the topologically inequivalent connected diagrams at the chosen order,
- render each diagram as SVG,
- stop before any matrix element calculation.

The implementation is based on the chapter 13 QED rules in
`book_sources/Chapter_13_QED.pdf/markdown.md`, especially:

- rule 6: each QED vertex is one photon plus two fermion legs,
- rule 7: include all topologically inequivalent arrangements,
- rule 8: identical-fermion interchange matters for amplitudes,
- rule 9: fermion loops carry a minus sign.

## What It Supports

The current generator supports `2 -> 2` QED processes involving:

- electrons and positrons: `e-`, `e+`
- muons and antimuons: `mu-`, `mu+`
- taus and antitaus: `tau-`, `tau+`
- photons: `gamma`

Supported process classes:

- charged-fermion scattering via virtual photon exchange
- particle-antiparticle scattering and annihilation channels
- Compton-like fermion-photon scattering
- pair annihilation into two photons
- pair production from two photons
- one-loop vacuum-polarization corrections on four-fermion photon-exchange diagrams

Examples:

- `e- + mu- -> e- + mu-`
- `e- + e+ -> e- + e+`
- `e- + e- -> e- + e-`
- `e- + gamma -> e- + gamma`
- `e- + e+ -> mu- + mu+`
- `e- + e+ -> gamma + gamma`
- `gamma + gamma -> e- + e+`

The parser also accepts compact input without spaces, for example:

- `e-+e+->mu-+mu+`

## Orders

You can currently choose:

- `tree`: lowest non-zero order tree diagrams
- `one-loop`: vacuum-polarization bubble insertions on virtual-photon exchange diagrams for four-fermion reactions

Examples that work in `one-loop` mode:

- `e- + mu- -> e- + mu-`
- `e- + e+ -> e- + e+`
- `e- + e+ -> mu- + mu+`

## What It Does Not Support Yet

- matrix element or cross-section calculations
- one-loop Compton or pair-annihilation corrections
- vertex-correction and self-energy topologies
- higher-loop orders
- reactions with more than four external legs
- weak or strong interaction vertices
- fully free-form manual diagram editing

The browser UI is an editor in the limited sense that you can enter reactions, choose the
perturbative order, switch layout and label options, cycle through the resulting diagrams in a
carousel, and export the SVG drawings.

## Run The Browser UI

From the repository root:

```bash
python3 -m qed_diagrams serve
```

Then open:

```text
http://127.0.0.1:8000
```

## Generate SVG Files From The CLI

```bash
python3 -m qed_diagrams render "e- + e+ -> mu- + mu+" --order tree --output-dir generated_diagrams
```

Optional flags:

- `--order tree`
- `--order one-loop`
- `--compact`
- `--show-leg-ids`
- `--hide-momenta`

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The test suite covers the main chapter-style examples:

- electron-muon scattering
- Bhabha scattering
- Moller scattering
- Compton scattering
- annihilation into another lepton pair
- annihilation into two photons
- one-loop vacuum polarization on four-fermion scattering
- invalid tree-level reactions

## Project Layout

- `qed_diagrams/core.py`: reaction parser and lowest-order topology generator
- `qed_diagrams/render.py`: SVG renderer
- `qed_diagrams/web.py`: zero-dependency local browser UI
- `qed_diagrams/__main__.py`: CLI entry point
- `tests/test_qed_diagrams.py`: unit tests

## Next Useful Extensions

The natural next steps are:

1. add explicit topological weights and symmetry metadata,
2. add one-loop vertex-correction and self-energy diagrams beyond vacuum polarization,
3. add a genuine drag-based visual editor on top of the generated graph structure,
4. broaden the parser to more symbolic reaction notation.
