from __future__ import annotations

import unittest

from qed_diagrams.amplitude import generate_symbolic_amplitudes
from qed_diagrams.core import DiagramGenerationError, generate_diagrams
from qed_diagrams.render import render_diagram_svg
from qed_diagrams.web import HTML_PAGE


class DiagramGeneratorTests(unittest.TestCase):
    def test_electron_muon_scattering_has_one_t_channel_diagram(self) -> None:
        bundle = generate_diagrams("e- + mu- -> e- + mu-")
        self.assertEqual(len(bundle.diagrams), 1)
        self.assertEqual(bundle.diagrams[0].channel, "t")
        self.assertEqual(bundle.diagrams[0].topology, "photon_exchange")

    def test_bhabha_scattering_has_s_and_t_channels(self) -> None:
        bundle = generate_diagrams("e- + e+ -> e- + e+")
        self.assertEqual([diagram.channel for diagram in bundle.diagrams], ["s", "t"])

    def test_moller_scattering_has_t_and_u_channels(self) -> None:
        bundle = generate_diagrams("e- + e- -> e- + e-")
        self.assertEqual([diagram.channel for diagram in bundle.diagrams], ["t", "u"])

    def test_compton_scattering_has_s_and_u_channels(self) -> None:
        bundle = generate_diagrams("e- + gamma -> e- + gamma")
        self.assertEqual([diagram.channel for diagram in bundle.diagrams], ["s", "u"])
        self.assertTrue(all(diagram.topology == "fermion_exchange" for diagram in bundle.diagrams))

    def test_annihilation_to_muons_has_one_s_channel_diagram(self) -> None:
        bundle = generate_diagrams("e- + e+ -> mu- + mu+")
        self.assertEqual(len(bundle.diagrams), 1)
        self.assertEqual(bundle.diagrams[0].channel, "s")

    def test_pair_annihilation_to_two_photons_has_two_diagrams(self) -> None:
        bundle = generate_diagrams("e- + e+ -> gamma + gamma")
        self.assertEqual([diagram.channel for diagram in bundle.diagrams], ["t", "u"])

    def test_one_loop_vacuum_polarization_is_available_for_four_fermion_scattering(self) -> None:
        bundle = generate_diagrams("e- + e+ -> e- + e+", order="one-loop")
        self.assertEqual(bundle.order, "one-loop")
        self.assertTrue(all(diagram.correction == "vacuum_polarization" for diagram in bundle.diagrams))

    def test_one_loop_mode_rejects_external_photon_processes_for_now(self) -> None:
        with self.assertRaises(DiagramGenerationError):
            generate_diagrams("e- + gamma -> e- + gamma", order="one-loop")

    def test_compact_reaction_syntax_without_spaces_is_supported(self) -> None:
        bundle = generate_diagrams("e-+e+->mu-+mu+")
        self.assertEqual(len(bundle.diagrams), 1)
        self.assertEqual(bundle.diagrams[0].channel, "s")

    def test_invalid_family_change_is_rejected(self) -> None:
        with self.assertRaises(DiagramGenerationError):
            generate_diagrams("e- + gamma -> mu- + gamma")

    def test_tree_level_photon_photon_scattering_is_rejected(self) -> None:
        with self.assertRaises(DiagramGenerationError):
            generate_diagrams("gamma + gamma -> gamma + gamma")

    def test_svg_render_contains_svg_root(self) -> None:
        bundle = generate_diagrams("e- + e+ -> mu- + mu+")
        svg = render_diagram_svg(bundle, bundle.diagrams[0])
        self.assertIn("<svg", svg)
        self.assertIn("p1", svg)
        self.assertIn("q1", svg)

    def test_pair_production_symbolic_amplitude_has_t_and_u_terms(self) -> None:
        amplitude = generate_symbolic_amplitudes("gamma + gamma -> e- + e+")
        self.assertEqual([term.label for term in amplitude.terms], ["t", "u"])
        self.assertIn(r"\varepsilon_{\alpha}", amplitude.terms[0].expression)
        self.assertIn(r"\frac{d^4 q_{1}}{(2\pi)^4}", amplitude.terms[0].expression)
        self.assertIn(r"\gamma \cdot q_{1} + m_e", amplitude.terms[0].expression)
        self.assertIn(r"-i \mathcal{M} = \left(-i \mathcal{M}_{t}\right) + \left(-i \mathcal{M}_{u}\right)", amplitude.total_expression)

    def test_bhabha_symbolic_total_amplitude_subtracts_terms(self) -> None:
        amplitude = generate_symbolic_amplitudes("e- + e+ -> e- + e+")
        self.assertIn(r"- \left(-i \mathcal{M}_{t}\right)", amplitude.total_expression)

    def test_symbolic_amplitudes_are_tree_only(self) -> None:
        with self.assertRaises(DiagramGenerationError):
            generate_symbolic_amplitudes("e- + e+ -> e- + e+", order="one-loop")

    def test_web_ui_includes_mathjax_formula_rendering(self) -> None:
        self.assertIn("mathjax@3", HTML_PAGE)
        self.assertIn('class="formula-math"', HTML_PAGE)
        self.assertIn("typesetPromise", HTML_PAGE)


if __name__ == "__main__":
    unittest.main()
