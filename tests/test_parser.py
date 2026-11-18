"""
Tests for parser.py (Algorithm 4.44): accepted strings, rejected strings,
the trace of Dragon Book Figure 4.38, parse trees, rightmost derivations
and conflict handling.

Run from the project folder:   python tests/test_parser.py
"""

import os
import sys
import unittest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "lr_parser"))

from grammar import load_grammar, EPSILON
from lr0 import canonical_collection
from tables import build_slr_table
from parser import parse, rightmost_derivation

GRAMMAR_DIR = os.path.join(PROJECT_DIR, "grammars")


def slr_parse(filename, text, resolve_conflicts=False):
    """Build the SLR table for a grammar file and parse a space-separated string."""
    g = load_grammar(os.path.join(GRAMMAR_DIR, filename))
    states, transitions = canonical_collection(g)
    action, goto_table = build_slr_table(g, states, transitions)
    return g, parse(g, action, goto_table, text.split(), resolve_conflicts)


class TestFigure438(unittest.TestCase):
    """Example 4.45: the moves for  id * id + id  must match Figure 4.38 line by line."""

    def test_trace(self):
        g, result = slr_parse("expr.txt", "id * id + id")
        expected = [
            ("0",        "",       "id * id + id $", "shift"),
            ("0 5",      "id",     "* id + id $",    "reduce by F -> id"),
            ("0 3",      "F",      "* id + id $",    "reduce by T -> F"),
            ("0 2",      "T",      "* id + id $",    "shift"),
            ("0 2 7",    "T *",    "id + id $",      "shift"),
            ("0 2 7 5",  "T * id", "+ id $",         "reduce by F -> id"),
            ("0 2 7 10", "T * F",  "+ id $",         "reduce by T -> T * F"),
            ("0 2",      "T",      "+ id $",         "reduce by E -> T"),
            ("0 1",      "E",      "+ id $",         "shift"),
            ("0 1 6",    "E +",    "id $",           "shift"),
            ("0 1 6 5",  "E + id", "$",              "reduce by F -> id"),
            ("0 1 6 3",  "E + F",  "$",              "reduce by T -> F"),
            ("0 1 6 9",  "E + T",  "$",              "reduce by E -> E + T"),
            ("0 1",      "E",      "$",              "accept"),
        ]
        self.assertTrue(result.accepted)
        self.assertEqual(result.steps, expected)

    def test_rightmost_derivation(self):
        g, result = slr_parse("expr.txt", "id * id + id")
        forms = [" ".join(f) for f in rightmost_derivation(g, result.reductions)]
        self.assertEqual(forms, [
            "E", "E + T", "E + F", "E + id", "T + id",
            "T * F + id", "T * id + id", "F * id + id", "id * id + id"])

    def test_parse_tree(self):
        g, result = slr_parse("expr.txt", "id * id + id")
        root = result.tree
        self.assertEqual(root.symbol, "E")
        self.assertEqual([c.symbol for c in root.children], ["E", "+", "T"])
        self.assertEqual(root.leaves(), ["id", "*", "id", "+", "id"])


class TestAccepted(unittest.TestCase):

    def check_accepts(self, filename, text):
        g, result = slr_parse(filename, text)
        self.assertTrue(result.accepted, f"{text!r} should be accepted: {result.error}")
        # The leaves of the tree (without epsilon) must spell the input again
        leaves = [x for x in result.tree.leaves() if x != EPSILON]
        self.assertEqual(leaves, text.split())
        # The last sentential form of the derivation is the input itself
        self.assertEqual(rightmost_derivation(g, result.reductions)[-1], text.split())
        return result

    def test_expression_strings(self):
        for text in ["id", "id + id", "id * id", "( id )", "( id + id ) * id",
                     "id * ( id + id * id ) + id", "( ( id ) )"]:
            self.check_accepts("expr.txt", text)

    def test_epsilon_grammar(self):
        for text in ["id", "id + id", "id * id + id", "( id + id ) * id"]:
            self.check_accepts("epsilon.txt", text)

    def test_epsilon_reductions_appear_in_tree(self):
        result = self.check_accepts("epsilon.txt", "id")
        # E -> T E',  T -> F T',  T' -> epsilon,  E' -> epsilon
        self.assertEqual(result.tree.leaves(), ["id", EPSILON, EPSILON])
        self.assertIn(3, result.reductions)  # (3) E' -> epsilon
        self.assertIn(6, result.reductions)  # (6) T' -> epsilon


class TestRejected(unittest.TestCase):

    def check_rejects(self, text, position, expected):
        g, result = slr_parse("expr.txt", text)
        self.assertFalse(result.accepted)
        self.assertEqual(result.error_position, position)
        self.assertEqual(result.expected, expected)
        return result

    def test_missing_operand(self):
        self.check_rejects("id + * id", 3, ["(", "id"])

    def test_two_ids_in_a_row(self):
        self.check_rejects("id id", 2, ["+", "*", ")", "$"])

    def test_starts_with_operator(self):
        self.check_rejects("+ id", 1, ["(", "id"])

    def test_unclosed_parenthesis(self):
        result = self.check_rejects("( id + id", 5, ["+", ")"])
        self.assertIn("end of input", result.error)

    def test_extra_close_parenthesis(self):
        # ')' is in FOLLOW(F), FOLLOW(T) and FOLLOW(E), so the SLR parser first
        # reduces id -> F -> T -> E and only detects the error in state 1,
        # whose ACTION row has just '+' and '$'.
        result = self.check_rejects("id )", 2, ["+", "$"])
        self.assertEqual(result.steps[-1][0], "0 1")

    def test_empty_input(self):
        self.check_rejects("", 1, ["(", "id"])

    def test_unknown_token(self):
        # Checked before parsing starts, so no parser moves and no expected list
        result = self.check_rejects("id x id", 2, [])
        self.assertIn("not a terminal", result.error)
        self.assertEqual(result.steps, [])

    def test_epsilon_grammar_rejects(self):
        g, result = slr_parse("epsilon.txt", "id + + id")
        self.assertFalse(result.accepted)
        self.assertEqual(result.error_position, 3)


class TestConflictHandling(unittest.TestCase):

    def test_refuses_table_with_conflicts(self):
        g, result = slr_parse("slr_conflict.txt", "* id = id")
        self.assertFalse(result.accepted)
        self.assertEqual(result.steps, [])          # did not even start
        self.assertIn("conflict", result.error)

    def test_resolve_prefers_shift(self):
        g, result = slr_parse("slr_conflict.txt", "* id = id", resolve_conflicts=True)
        self.assertTrue(result.accepted)
        notes = [step[3] for step in result.steps if "conflict" in step[3]]
        self.assertEqual(len(notes), 1)
        self.assertIn("chose s6", notes[0])

    def test_resolve_reduce_reduce_takes_earliest_production(self):
        g, result = slr_parse("reduce_reduce.txt", "a", resolve_conflicts=True)
        self.assertTrue(result.accepted)
        self.assertEqual(result.reductions[0], 3)   # (3) A -> a, not (4) B -> a


if __name__ == "__main__":
    unittest.main(verbosity=2)
