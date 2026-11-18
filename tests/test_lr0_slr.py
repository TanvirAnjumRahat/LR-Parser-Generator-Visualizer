"""
Checks lr0.py and tables.py against the Dragon Book:
  - Figure 4.31: LR(0) automaton for the expression grammar (states I0..I11)
  - Figure 4.37: SLR parsing table for the expression grammar
  - Example 4.48: grammar (4.49) has a shift-reduce conflict on '=' in state 2

Run from the project folder:   python tests/test_lr0_slr.py
"""

import os
import sys
import unittest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "lr_parser"))

from grammar import load_grammar
from lr0 import canonical_collection
from tables import build_slr_table, find_conflicts

GRAMMAR_DIR = os.path.join(PROJECT_DIR, "grammars")


def build(filename):
    g = load_grammar(os.path.join(GRAMMAR_DIR, filename))
    states, transitions = canonical_collection(g)
    action, goto_table = build_slr_table(g, states, transitions)
    return g, states, transitions, action, goto_table


def kernel_strings(g, items):
    return {str(item) for item in items if item.is_kernel(g)}


class TestFigure431(unittest.TestCase):
    """The 12 LR(0) states of the expression grammar, numbered as in Fig. 4.31."""

    def setUp(self):
        self.g, self.states, self.trans, _, _ = build("expr.txt")

    def test_kernels(self):
        expected = [
            {"E' -> · E"},
            {"E' -> E ·", "E -> E · + T"},
            {"E -> T ·", "T -> T · * F"},
            {"T -> F ·"},
            {"F -> ( · E )"},
            {"F -> id ·"},
            {"E -> E + · T"},
            {"T -> T * · F"},
            {"F -> ( E · )", "E -> E · + T"},
            {"E -> E + T ·", "T -> T · * F"},
            {"T -> T * F ·"},
            {"F -> ( E ) ·"},
        ]
        self.assertEqual(len(self.states), 12)
        for i in range(12):
            self.assertEqual(kernel_strings(self.g, self.states[i]), expected[i], f"state I{i}")

    def test_full_closure_of_I0(self):
        self.assertEqual({str(x) for x in self.states[0]}, {
            "E' -> · E", "E -> · E + T", "E -> · T", "T -> · T * F",
            "T -> · F", "F -> · ( E )", "F -> · id"})

    def test_transitions(self):
        expected = {
            (0, "E"): 1, (0, "T"): 2, (0, "F"): 3, (0, "("): 4, (0, "id"): 5,
            (1, "+"): 6, (2, "*"): 7,
            (4, "E"): 8, (4, "T"): 2, (4, "F"): 3, (4, "("): 4, (4, "id"): 5,
            (6, "T"): 9, (6, "F"): 3, (6, "("): 4, (6, "id"): 5,
            (7, "F"): 10, (7, "("): 4, (7, "id"): 5,
            (8, ")"): 11, (8, "+"): 6, (9, "*"): 7,
        }
        self.assertEqual(self.trans, expected)


class TestFigure437(unittest.TestCase):
    """SLR table for the expression grammar, exactly as in Fig. 4.37."""

    def test_table(self):
        g, states, trans, action, goto_table = build("expr.txt")
        expected_action = {
            0: {"id": "s5", "(": "s4"},
            1: {"+": "s6", "$": "acc"},
            2: {"+": "r2", "*": "s7", ")": "r2", "$": "r2"},
            3: {"+": "r4", "*": "r4", ")": "r4", "$": "r4"},
            4: {"id": "s5", "(": "s4"},
            5: {"+": "r6", "*": "r6", ")": "r6", "$": "r6"},
            6: {"id": "s5", "(": "s4"},
            7: {"id": "s5", "(": "s4"},
            8: {"+": "s6", ")": "s11"},
            9: {"+": "r1", "*": "s7", ")": "r1", "$": "r1"},
            10: {"+": "r3", "*": "r3", ")": "r3", "$": "r3"},
            11: {"+": "r5", "*": "r5", ")": "r5", "$": "r5"},
        }
        # Turn our table (cells hold a dict of actions) into state -> {symbol: act}
        actual_action = {i: {} for i in range(len(states))}
        for (i, a), cell in action.items():
            self.assertEqual(len(cell), 1, f"unexpected conflict at ({i}, {a})")
            actual_action[i][a] = list(cell.keys())[0]
        self.assertEqual(actual_action, expected_action)

        expected_goto = {
            (0, "E"): 1, (0, "T"): 2, (0, "F"): 3,
            (4, "E"): 8, (4, "T"): 2, (4, "F"): 3,
            (6, "T"): 9, (6, "F"): 3,
            (7, "F"): 10,
        }
        self.assertEqual(goto_table, expected_goto)
        self.assertEqual(find_conflicts(action), [])


class TestEpsilonGrammarSLR(unittest.TestCase):
    """The epsilon bug is fixed: E' -> · and T' -> · become reduce actions."""

    def test_no_crash_and_no_conflicts(self):
        g, states, trans, action, goto_table = build("epsilon.txt")
        self.assertEqual(find_conflicts(action), [])
        # State 2 = { E -> T · E', E' -> · + T E', E' -> · }: reduce by (3) E' -> epsilon
        self.assertEqual(list(action[(2, ")")].keys()), ["r3"])
        self.assertEqual(list(action[(2, "$")].keys()), ["r3"])
        self.assertEqual(list(action[(2, "+")].keys()), ["s7"])


class TestConflicts(unittest.TestCase):

    def test_example_448_shift_reduce(self):
        g, states, trans, action, goto_table = build("slr_conflict.txt")
        conflicts = find_conflicts(action)
        self.assertEqual(len(conflicts), 1)
        c = conflicts[0]
        self.assertEqual((c["state"], c["symbol"], c["kind"]), (2, "=", "shift-reduce"))
        self.assertEqual(set(c["cell"].keys()), {"s6", "r5"})

    def test_reduce_reduce(self):
        g, states, trans, action, goto_table = build("reduce_reduce.txt")
        conflicts = find_conflicts(action)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["kind"], "reduce-reduce")
        self.assertEqual(set(conflicts[0]["cell"].keys()), {"r3", "r4"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
