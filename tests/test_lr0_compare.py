"""
Phase 6 tests: the LR(0) table and the comparison report of all four methods.

Run from the project folder:   python tests/test_lr0_compare.py
"""

import os
import sys
import unittest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "lr_parser"))

from grammar import load_grammar
from tables import build_parsing_table, compare_methods, METHOD_NAMES
from parser import parse_text

GRAMMAR_DIR = os.path.join(PROJECT_DIR, "grammars")


def load(filename):
    return load_grammar(os.path.join(GRAMMAR_DIR, filename))


class TestLR0Table(unittest.TestCase):

    def test_expression_grammar_is_not_lr0(self):
        # States 2 = {E -> T ·, T -> T · * F} and 9 = {E -> E + T ·, T -> T · * F}:
        # LR(0) reduces on '*' too, which clashes with the shift on '*'.
        table = build_parsing_table(load("expr.txt"), "lr0")
        places = {(c["state"], c["symbol"], c["kind"]) for c in table.conflicts}
        self.assertEqual(places, {(2, "*", "shift-reduce"), (9, "*", "shift-reduce")})

    def test_reduce_on_every_terminal(self):
        g = load("expr.txt")
        table = build_parsing_table(g, "lr0")
        # state 3 = {T -> F ·}: r4 on all terminals and $
        for a in g.terminals + ["$"]:
            self.assertEqual(list(table.action[(3, a)].keys()), ["r4"])

    def test_lr0_has_same_states_as_slr(self):
        for filename in ["expr.txt", "epsilon.txt", "cc.txt", "slr_conflict.txt"]:
            g = load(filename)
            self.assertEqual(len(build_parsing_table(g, "lr0").states),
                             len(build_parsing_table(g, "slr").states))

    def test_cc_is_lr0_and_parses(self):
        g = load("cc.txt")
        table = build_parsing_table(g, "lr0")
        self.assertEqual(table.conflicts, [])
        self.assertTrue(parse_text(g, table.action, table.goto_table, "c d d").accepted)
        self.assertFalse(parse_text(g, table.action, table.goto_table, "c d").accepted)

    def test_epsilon_rules_conflict_in_lr0(self):
        # E' -> · is complete in the same state as the shift on '+'
        table = build_parsing_table(load("epsilon.txt"), "lr0")
        self.assertEqual(len(table.conflicts), 4)


class TestComparison(unittest.TestCase):
    """The verdicts show the hierarchy LR(0) < SLR(1) < LALR(1) < CLR(1)."""

    EXPECTED = {
        # grammar               LR(0)  SLR(1) LALR(1) CLR(1)
        "cc.txt":              ["yes", "yes", "yes", "yes"],
        "expr.txt":            ["no",  "yes", "yes", "yes"],
        "expr_num.txt":        ["no",  "yes", "yes", "yes"],
        "epsilon.txt":         ["no",  "yes", "yes", "yes"],
        "slr_conflict.txt":    ["no",  "no",  "yes", "yes"],
        "lalr_conflict.txt":   ["no",  "no",  "no",  "yes"],
        "reduce_reduce.txt":   ["no",  "no",  "no",  "no"],
        "dangling_else.txt":   ["no",  "no",  "no",  "no"],
        "ambiguous_expr.txt":  ["no",  "no",  "no",  "no"],
        "ambiguous_expr_prec.txt": ["no (usable with precedence)"] * 4,
    }

    def test_verdicts_for_all_demo_grammars(self):
        for filename, expected in self.EXPECTED.items():
            rows = compare_methods(load(filename))
            self.assertEqual([r["method"] for r in rows], list(METHOD_NAMES.keys()))
            self.assertEqual([r["verdict"] for r in rows], expected, filename)

    def test_every_demo_grammar_is_covered(self):
        files = {f for f in os.listdir(GRAMMAR_DIR) if f.endswith(".txt")}
        self.assertEqual(files, set(self.EXPECTED.keys()))

    def test_state_counts(self):
        rows = compare_methods(load("cc.txt"))
        self.assertEqual([r["states"] for r in rows], [7, 7, 7, 10])

    def test_conflict_kinds_are_counted(self):
        rows = compare_methods(load("lalr_conflict.txt"))
        lalr = rows[2]
        self.assertEqual((lalr["shift_reduce"], lalr["reduce_reduce"]), (0, 2))


class TestAmbiguousGrammars(unittest.TestCase):
    """Dangling-else and the ambiguous expression grammar conflict in EVERY method."""

    def test_conflicts_in_every_method(self):
        for filename in ["dangling_else.txt", "ambiguous_expr.txt"]:
            g = load(filename)
            for method in METHOD_NAMES:
                table = build_parsing_table(g, method)
                self.assertGreater(len(table.conflicts), 0, (filename, method))
                for c in table.conflicts:
                    self.assertEqual(c["kind"], "shift-reduce", (filename, method))

    def test_dangling_else_conflict_is_on_else(self):
        for method in METHOD_NAMES:
            table = build_parsing_table(load("dangling_else.txt"), method)
            self.assertEqual({c["symbol"] for c in table.conflicts}, {"e"}, method)

    def test_dangling_else_shift_matches_nearest_if(self):
        g = load("dangling_else.txt")
        table = build_parsing_table(g, "lalr")
        result = parse_text(g, table.action, table.goto_table, "i b t i b t a e a",
                            resolve_conflicts=True)
        self.assertTrue(result.accepted)
        outer = result.tree
        # outer if has no else (4 children); the inner if got the else (6 children)
        self.assertEqual([c.symbol for c in outer.children], ["i", "E", "t", "S"])
        self.assertEqual([c.symbol for c in outer.children[3].children],
                         ["i", "E", "t", "S", "e", "S"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
