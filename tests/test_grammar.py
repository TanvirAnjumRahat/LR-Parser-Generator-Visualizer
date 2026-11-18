"""
Checks grammar.py's FIRST and FOLLOW sets against the Dragon Book values.

Run from the project folder:   python tests/test_grammar.py
"""

import os
import sys
import unittest

# Let us import lr_parser/grammar.py
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "lr_parser"))

from grammar import load_grammar, parse_grammar_lines, Grammar, EPSILON

GRAMMAR_DIR = os.path.join(PROJECT_DIR, "grammars")


class TestExpressionGrammar(unittest.TestCase):
    """Grammar (4.1): E -> E + T | T,  T -> T * F | F,  F -> ( E ) | id"""

    def setUp(self):
        self.g = load_grammar(os.path.join(GRAMMAR_DIR, "expr.txt"))

    def test_symbols(self):
        self.assertEqual(self.g.non_terminals, ["E'", "E", "T", "F"])
        self.assertEqual(self.g.terminals, ["+", "*", "(", ")", "id"])
        self.assertEqual(self.g.productions[0], ("E'", ["E"]))
        self.assertEqual(len(self.g.productions), 7)  # S'->S plus 6 rules

    def test_first(self):
        # Same as the non-left-recursive version: FIRST = { (, id }
        for nt in ["E'", "E", "T", "F"]:
            self.assertEqual(self.g.first[nt], {"(", "id"})

    def test_follow(self):
        # Dragon Book Example 4.30 / SLR table in Fig. 4.37 uses these.
        self.assertEqual(self.g.follow["E'"], {"$"})
        self.assertEqual(self.g.follow["E"], {"+", ")", "$"})
        self.assertEqual(self.g.follow["T"], {"+", "*", ")", "$"})
        self.assertEqual(self.g.follow["F"], {"+", "*", ")", "$"})


class TestEpsilonGrammar(unittest.TestCase):
    """Grammar (4.28), values from Dragon Book Example 4.30."""

    def setUp(self):
        self.g = load_grammar(os.path.join(GRAMMAR_DIR, "epsilon.txt"))

    def test_augmented_name_does_not_clash(self):
        # E' is already a non-terminal, so S' must become E''
        self.assertEqual(self.g.augmented_start, "E''")

    def test_epsilon_stored_as_empty_list(self):
        self.assertIn(("E'", []), self.g.productions)
        self.assertIn(("T'", []), self.g.productions)

    def test_first(self):
        self.assertEqual(self.g.first["F"], {"(", "id"})
        self.assertEqual(self.g.first["T"], {"(", "id"})
        self.assertEqual(self.g.first["E"], {"(", "id"})
        self.assertEqual(self.g.first["E'"], {"+", EPSILON})
        self.assertEqual(self.g.first["T'"], {"*", EPSILON})

    def test_follow(self):
        self.assertEqual(self.g.follow["E"], {")", "$"})
        self.assertEqual(self.g.follow["E'"], {")", "$"})
        self.assertEqual(self.g.follow["T"], {"+", ")", "$"})
        self.assertEqual(self.g.follow["T'"], {"+", ")", "$"})
        self.assertEqual(self.g.follow["F"], {"+", "*", ")", "$"})


class TestNullableChain(unittest.TestCase):
    """S -> A B c,  A -> a | epsilon,  B -> b | epsilon : epsilon passes through A and B."""

    def test_first_and_follow(self):
        g = Grammar(parse_grammar_lines([
            "S -> A B c",
            "A -> a | epsilon",
            "B -> b | epsilon",
        ]))
        self.assertEqual(g.first["S"], {"a", "b", "c"})
        self.assertEqual(g.first["A"], {"a", EPSILON})
        self.assertEqual(g.follow["A"], {"b", "c"})
        self.assertEqual(g.follow["B"], {"c"})
        self.assertEqual(g.follow["S"], {"$"})

    def test_bad_line_reports_error(self):
        with self.assertRaises(ValueError):
            parse_grammar_lines(["S a b"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
