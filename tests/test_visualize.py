"""
Tests for visualize.py: the LR(0) automaton drawing is checked against
Dragon Book Figure 4.31 by reading the generated DOT source, and output
file naming is checked.

Run from the project folder:   python tests/test_visualize.py
"""

import os
import re
import sys
import tempfile
import unittest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "lr_parser"))

from grammar import load_grammar
from lr0 import canonical_collection
from tables import build_slr_table, find_conflicts
from parser import parse_text
from visualize import (automaton_graph, parse_tree_graph, save_graph,
                       output_base_name, accept_state_number)

GRAMMAR_DIR = os.path.join(PROJECT_DIR, "grammars")


def build_automaton(filename):
    g = load_grammar(os.path.join(GRAMMAR_DIR, filename))
    states, transitions = canonical_collection(g)
    action, goto_table = build_slr_table(g, states, transitions)
    conflict_states = set()
    for c in find_conflicts(action):
        conflict_states.add(c["state"])
    graph = automaton_graph(g, states, transitions, conflict_states)
    return g, states, transitions, graph.source


def edges_in(source):
    """All 'Ii -> Ij [label=<X>]' edges in the DOT source, as (i, X, j)."""
    found = set()
    for i, j, label in re.findall(r"I(\d+) -> I(\d+) \[label=<([^>]*)>\]", source):
        found.add((int(i), label, int(j)))
    return found


def node_line(source, name):
    """The DOT line that defines node 'name' (e.g. 'I2')."""
    for line in source.splitlines():
        if line.strip().startswith(name + " [label="):
            return line
    return ""


class TestFigure431Drawing(unittest.TestCase):

    def setUp(self):
        self.g, self.states, self.transitions, self.source = build_automaton("expr.txt")

    def test_twelve_state_boxes(self):
        for i in range(12):
            self.assertNotEqual(node_line(self.source, f"I{i}"), "", f"I{i} missing")
        self.assertEqual(node_line(self.source, "I12"), "")

    def test_edges_match_figure_431(self):
        expected = {
            (0, "E", 1), (0, "T", 2), (0, "F", 3), (0, "(", 4), (0, "id", 5),
            (1, "+", 6), (2, "*", 7),
            (4, "E", 8), (4, "T", 2), (4, "F", 3), (4, "(", 4), (4, "id", 5),
            (6, "T", 9), (6, "F", 3), (6, "(", 4), (6, "id", 5),
            (7, "F", 10), (7, "(", 4), (7, "id", 5),
            (8, ")", 11), (8, "+", 6), (9, "*", 7),
        }
        self.assertEqual(edges_in(self.source), expected)

    def test_accept_state_is_I1(self):
        self.assertEqual(accept_state_number(self.g, self.states), 1)
        self.assertIn("I1 -> accept [label=\"$\"]", self.source)
        self.assertIn("(accept)", node_line(self.source, "I1"))

    def test_kernel_and_closure_items_separated(self):
        i0 = node_line(self.source, "I0")
        # kernel item, then the <HR/> line, then the six closure items
        self.assertLess(i0.index("E' -&gt; · E"), i0.index("<HR/>"))
        self.assertLess(i0.index("<HR/>"), i0.index("F -&gt; · id"))
        # I5 has only a kernel item, so no separator line
        self.assertNotIn("<HR/>", node_line(self.source, "I5"))

    def test_no_red_states_without_conflicts(self):
        self.assertNotIn('COLOR="red"', self.source)


class TestConflictDrawing(unittest.TestCase):

    def test_state_2_is_red(self):
        g, states, transitions, source = build_automaton("slr_conflict.txt")
        self.assertIn('COLOR="red"', node_line(source, "I2"))
        self.assertIn("(conflict)", node_line(source, "I2"))
        for i in range(len(states)):
            if i != 2:
                self.assertNotIn('COLOR="red"', node_line(source, f"I{i}"))


class TestLR1Drawing(unittest.TestCase):
    """Phase 5: LR(1) and LALR(1) automata show lookaheads and merged states."""

    def draw(self, method):
        from tables import build_parsing_table
        g = load_grammar(os.path.join(GRAMMAR_DIR, "cc.txt"))
        t = build_parsing_table(g, method)
        return automaton_graph(g, t.states, t.transitions, t.conflict_states(),
                               merged_from=t.merged_from).source

    def test_clr_items_show_lookaheads(self):
        source = self.draw("clr")
        self.assertIn("C -&gt; c · C, c/d", node_line(source, "I3"))
        self.assertIn("C -&gt; c · C, $", node_line(source, "I6"))

    def test_lalr_states_show_merged_lookaheads_and_origin(self):
        source = self.draw("lalr")
        self.assertIn("C -&gt; c · C, c/d/$", node_line(source, "I3"))
        self.assertIn("I3 + I6 of LR(1)", node_line(source, "I3"))
        self.assertEqual(node_line(source, "I7"), "")       # only 7 states: I0..I6


class TestParseTreeDrawing(unittest.TestCase):

    def test_leaves_show_lexemes(self):
        g = load_grammar(os.path.join(GRAMMAR_DIR, "expr_num.txt"))
        states, transitions = canonical_collection(g)
        action, goto_table = build_slr_table(g, states, transitions)
        result = parse_text(g, action, goto_table, "count + 10")
        source = parse_tree_graph(g, result.tree).source
        self.assertIn('"id (count)" shape=box', source)
        self.assertIn('"num (10)" shape=box', source)


class TestOutputNames(unittest.TestCase):

    def test_named_after_grammar(self):
        self.assertEqual(output_base_name("grammars/expr.txt"), "expr")
        self.assertEqual(output_base_name(os.path.join("a", "b", "slr_conflict.txt")), "slr_conflict")

    def test_out_option_wins(self):
        self.assertEqual(output_base_name("grammars/expr.txt", "run2"), "run2")

    def test_save_writes_dot_file(self):
        g, states, transitions, source = build_automaton("expr.txt")
        graph = automaton_graph(g, states, transitions)
        with tempfile.TemporaryDirectory() as folder:
            save_graph(graph, "expr_automaton", out_dir=folder)
            self.assertTrue(os.path.exists(os.path.join(folder, "expr_automaton.dot")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
