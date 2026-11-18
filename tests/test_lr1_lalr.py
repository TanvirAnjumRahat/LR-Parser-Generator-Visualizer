"""
Phase 5 tests: LR(1) items, CLR(1) and LALR(1) tables, checked against the Dragon Book.
  - Figure 4.41: the 10 LR(1) states of grammar (4.55)
  - Figure 4.42: the CLR(1) table of grammar (4.55)
  - Figure 4.43: the LALR(1) table of grammar (4.55), states I36, I47, I89 merged
  - grammar (4.49): SLR has a conflict, CLR and LALR do not
  - Section 4.7.4: an LR(1) grammar where LALR merging creates reduce-reduce conflicts
  - error detection: CLR finds errors with no extra reductions

Run from the project folder:   python tests/test_lr1_lalr.py
"""

import os
import sys
import unittest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "lr_parser"))

from grammar import load_grammar
from lr0 import canonical_collection
from lr1 import closure_lr1, LR1Item, state_core
from tables import build_parsing_table
from parser import parse_text, reductions_before_error

GRAMMAR_DIR = os.path.join(PROJECT_DIR, "grammars")

ALL_GRAMMARS = ["expr.txt", "expr_num.txt", "epsilon.txt", "slr_conflict.txt",
                "reduce_reduce.txt", "cc.txt", "lalr_conflict.txt"]


def load(filename):
    return load_grammar(os.path.join(GRAMMAR_DIR, filename))


def item_strings(items):
    return {str(item) for item in items}


def table_as_dict(table):
    """ACTION table as {state: {symbol: action}}; fails if a cell has a conflict."""
    result = {i: {} for i in range(len(table.states))}
    for (i, a), cell in table.action.items():
        assert len(cell) == 1, f"conflict at ({i}, {a})"
        result[i][a] = list(cell.keys())[0]
    return result


class TestLR1Items(unittest.TestCase):

    def test_items_with_different_lookaheads_are_different(self):
        g = load("cc.txt")
        lhs, rhs = g.productions[3]          # C -> d
        self.assertNotEqual(LR1Item(3, lhs, rhs, 1, "c"), LR1Item(3, lhs, rhs, 1, "d"))
        self.assertEqual(LR1Item(3, lhs, rhs, 1, "c").core(), LR1Item(3, lhs, rhs, 1, "d").core())

    def test_closure_uses_first_of_beta_a(self):
        # [S -> · C C, $]: beta = "C", so the C-items get FIRST(C $) = {c, d}
        g = load("cc.txt")
        start = LR1Item(0, "S'", ["S"], 0, "$")
        self.assertEqual(item_strings(closure_lr1([start], g)), {
            "[S' -> · S, $]", "[S -> · C C, $]",
            "[C -> · c C, c]", "[C -> · c C, d]", "[C -> · d, c]", "[C -> · d, d]"})

    def test_closure_with_nullable_beta(self):
        # In the epsilon grammar, [E -> · T E', $]: FIRST(E' $) = {+, $}
        g = load("epsilon.txt")
        start = LR1Item(0, "E''", ["E"], 0, "$")
        t_items = {str(x) for x in closure_lr1([start], g) if x.lhs == "T"}
        self.assertEqual(t_items, {"[T -> · F T', +]", "[T -> · F T', $]"})


class TestFigure441(unittest.TestCase):
    """Grammar (4.55): the canonical LR(1) collection has 10 states, as in Figure 4.41."""

    def setUp(self):
        self.table = build_parsing_table(load("cc.txt"), "clr")

    def test_ten_states_with_book_items(self):
        expected = [
            {"[S' -> · S, $]", "[S -> · C C, $]", "[C -> · c C, c]", "[C -> · c C, d]",
             "[C -> · d, c]", "[C -> · d, d]"},
            {"[S' -> S ·, $]"},
            {"[S -> C · C, $]", "[C -> · c C, $]", "[C -> · d, $]"},
            {"[C -> c · C, c]", "[C -> c · C, d]", "[C -> · c C, c]", "[C -> · c C, d]",
             "[C -> · d, c]", "[C -> · d, d]"},
            {"[C -> d ·, c]", "[C -> d ·, d]"},
            {"[S -> C C ·, $]"},
            {"[C -> c · C, $]", "[C -> · c C, $]", "[C -> · d, $]"},
            {"[C -> d ·, $]"},
            {"[C -> c C ·, c]", "[C -> c C ·, d]"},
            {"[C -> c C ·, $]"},
        ]
        self.assertEqual(len(self.table.states), 10)
        for i in range(10):
            self.assertEqual(item_strings(self.table.states[i]), expected[i], f"I{i}")

    def test_transitions(self):
        self.assertEqual(self.table.transitions, {
            (0, "S"): 1, (0, "C"): 2, (0, "c"): 3, (0, "d"): 4,
            (2, "C"): 5, (2, "c"): 6, (2, "d"): 7,
            (3, "C"): 8, (3, "c"): 3, (3, "d"): 4,
            (6, "C"): 9, (6, "c"): 6, (6, "d"): 7,
        })

    def test_clr_table_figure_442(self):
        self.assertEqual(table_as_dict(self.table), {
            0: {"c": "s3", "d": "s4"},
            1: {"$": "acc"},
            2: {"c": "s6", "d": "s7"},
            3: {"c": "s3", "d": "s4"},
            4: {"c": "r3", "d": "r3"},
            5: {"$": "r1"},
            6: {"c": "s6", "d": "s7"},
            7: {"$": "r3"},
            8: {"c": "r2", "d": "r2"},
            9: {"$": "r2"},
        })
        self.assertEqual(self.table.goto_table,
                         {(0, "S"): 1, (0, "C"): 2, (2, "C"): 5, (3, "C"): 8, (6, "C"): 9})


class TestFigure443(unittest.TestCase):
    """LALR(1) for grammar (4.55): 7 states; book's I36, I47, I89 are our 3, 4, 6."""

    def setUp(self):
        self.table = build_parsing_table(load("cc.txt"), "lalr")

    def test_merged_states(self):
        self.assertEqual(len(self.table.states), 7)
        self.assertEqual(self.table.merged_from,
                         [[0], [1], [2], [3, 6], [4, 7], [5], [8, 9]])

    def test_merged_lookaheads(self):
        self.assertEqual(item_strings(self.table.states[4]),
                         {"[C -> d ·, c]", "[C -> d ·, d]", "[C -> d ·, $]"})

    def test_lalr_table(self):
        self.assertEqual(table_as_dict(self.table), {
            0: {"c": "s3", "d": "s4"},                  # book: s36, s47
            1: {"$": "acc"},
            2: {"c": "s3", "d": "s4"},
            3: {"c": "s3", "d": "s4"},                  # book state 36
            4: {"c": "r3", "d": "r3", "$": "r3"},       # book state 47
            5: {"$": "r1"},
            6: {"c": "r2", "d": "r2", "$": "r2"},       # book state 89
        })
        self.assertEqual(self.table.goto_table,
                         {(0, "S"): 1, (0, "C"): 2, (2, "C"): 5, (3, "C"): 6})


class TestGrammar449(unittest.TestCase):
    """slr_conflict.txt: not SLR(1), but CLR(1) and LALR(1)."""

    def test_methods(self):
        g = load("slr_conflict.txt")
        self.assertEqual(len(build_parsing_table(g, "slr").conflicts), 1)
        clr = build_parsing_table(g, "clr")
        lalr = build_parsing_table(g, "lalr")
        self.assertEqual(clr.conflicts, [])
        self.assertEqual(lalr.conflicts, [])
        self.assertEqual(len(clr.states), 14)
        self.assertEqual(len(lalr.states), 10)

    def test_state_2_reduces_only_on_dollar(self):
        # LR(1) state 2 = { [S -> L · = R, $], [R -> L ·, $] }: shift on '=', reduce only on $
        clr = build_parsing_table(load("slr_conflict.txt"), "clr")
        self.assertEqual(item_strings(clr.states[2]), {"[S -> L · = R, $]", "[R -> L ·, $]"})
        self.assertEqual(list(clr.action[(2, "=")].keys()), ["s6"])
        self.assertEqual(list(clr.action[(2, "$")].keys()), ["r5"])

    def test_parses_without_resolve(self):
        g = load("slr_conflict.txt")
        for method in ["clr", "lalr"]:
            t = build_parsing_table(g, method)
            for text in ["id", "* id", "id = id", "* id = * * id"]:
                self.assertTrue(parse_text(g, t.action, t.goto_table, text).accepted, (method, text))


class TestMergingCreatesConflicts(unittest.TestCase):
    """lalr_conflict.txt is LR(1) but merging creates reduce-reduce conflicts."""

    def test_clr_has_no_conflicts(self):
        self.assertEqual(build_parsing_table(load("lalr_conflict.txt"), "clr").conflicts, [])

    def test_lalr_reduce_reduce_from_merging(self):
        lalr = build_parsing_table(load("lalr_conflict.txt"), "lalr")
        self.assertEqual(len(lalr.conflicts), 2)
        for c in lalr.conflicts:
            self.assertEqual(c["kind"], "reduce-reduce")
            self.assertEqual(set(c["cell"].keys()), {"r5", "r6"})
            self.assertIn("note", c)                          # marked as created by merging
            self.assertEqual(lalr.merged_from[c["state"]], [6, 9])
        self.assertEqual({c["symbol"] for c in lalr.conflicts}, {"d", "e"})

    def test_conflicts_not_from_merging_are_not_marked(self):
        # reduce_reduce.txt already has the conflict in CLR, so LALR did not create it
        lalr = build_parsing_table(load("reduce_reduce.txt"), "lalr")
        self.assertEqual(len(lalr.conflicts), 1)
        self.assertNotIn("note", lalr.conflicts[0])


class TestLALRTheorems(unittest.TestCase):
    """Facts from Section 4.7 that must hold for every grammar."""

    def test_lalr_has_same_states_as_lr0(self):
        # LALR(1) states have exactly the cores of the LR(0) states
        for filename in ALL_GRAMMARS:
            g = load(filename)
            lr0_states, _ = canonical_collection(g)
            lalr = build_parsing_table(g, "lalr")
            self.assertEqual(len(lalr.states), len(lr0_states), filename)
            lr0_cores = {frozenset((x.prod_index, x.dot) for x in s) for s in lr0_states}
            lalr_cores = {state_core(s) for s in lalr.states}
            self.assertEqual(lalr_cores, lr0_cores, filename)

    def test_merging_never_creates_shift_reduce(self):
        for filename in ALL_GRAMMARS:
            g = load(filename)
            clr = build_parsing_table(g, "clr")
            lalr = build_parsing_table(g, "lalr")
            clr_kinds = {c["kind"] for c in clr.conflicts}
            for c in lalr.conflicts:
                if "shift-reduce" in c["kind"]:
                    self.assertIn("shift-reduce", " ".join(clr_kinds), filename)

    def test_all_methods_accept_the_same_strings(self):
        cases = {"expr.txt": ["id * id + id", "( id )", "id + ( id * id )"],
                 "epsilon.txt": ["id", "id + id * id", "( id + id ) * id"],
                 "cc.txt": ["d d", "c d d", "c c d c d"]}
        for filename, texts in cases.items():
            g = load(filename)
            for method in ["slr", "clr", "lalr"]:
                t = build_parsing_table(g, method)
                for text in texts:
                    r = parse_text(g, t.action, t.goto_table, text)
                    self.assertTrue(r.accepted, (filename, method, text, r.error))


class TestErrorDetection(unittest.TestCase):
    """CLR detects errors without the extra reductions SLR and LALR may do."""

    def run_all(self, filename, text):
        g = load(filename)
        results = {}
        for method in ["slr", "clr", "lalr"]:
            t = build_parsing_table(g, method)
            results[method] = parse_text(g, t.action, t.goto_table, text)
        return results

    def test_cc_book_example(self):
        r = self.run_all("cc.txt", "c c d")       # one C is missing
        for method in ["slr", "clr", "lalr"]:
            self.assertFalse(r[method].accepted)
            self.assertEqual(r[method].error_position, 4)   # all find it at the same token ($)
        self.assertEqual(reductions_before_error(r["clr"]), 0)
        self.assertEqual(reductions_before_error(r["slr"]), 3)
        self.assertEqual(reductions_before_error(r["lalr"]), 3)

    def test_expression_extra_parenthesis(self):
        r = self.run_all("expr.txt", "id )")
        self.assertEqual(reductions_before_error(r["clr"]), 0)
        self.assertEqual(reductions_before_error(r["slr"]), 3)
        self.assertEqual(reductions_before_error(r["lalr"]), 3)
        # CLR's expected tokens are exact for this context
        self.assertEqual(r["clr"].expected, ["+", "*", "$"])
        self.assertEqual(r["slr"].expected, ["+", "$"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
