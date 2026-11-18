"""
Phase 6 tests: %left / %right / %nonassoc (Dragon Book 4.8.1, Yacc 4.9.2).

Run from the project folder:   python tests/test_precedence.py
"""

import os
import sys
import unittest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "lr_parser"))

from grammar import Grammar, load_grammar, parse_grammar_lines, parse_precedence_lines
from tables import build_parsing_table, METHOD_NAMES
from parser import parse_text

GRAMMAR_DIR = os.path.join(PROJECT_DIR, "grammars")


def grammar_from_lines(lines):
    return Grammar(parse_grammar_lines(lines), parse_precedence_lines(lines))


def tree_text(node):
    """Fully parenthesized form of an expression tree: E -> E + E becomes (a + b)."""
    if not node.children:
        return node.symbol
    parts = [tree_text(c) for c in node.children]
    if len(parts) == 1:
        return parts[0]
    if parts[0] == "(":                       # E -> ( E ): keep the inner text
        return parts[1]
    return "(" + " ".join(parts) + ")"


def parse_with(g, text, method="lalr"):
    table = build_parsing_table(g, method)
    return table, parse_text(g, table.action, table.goto_table, text)


class TestDeclarations(unittest.TestCase):

    def test_later_lines_have_higher_precedence(self):
        prec = parse_precedence_lines(["%left + -", "%left * /", "%right ^", "E -> id"])
        self.assertEqual(prec, {"+": (1, "left"), "-": (1, "left"), "*": (2, "left"),
                                "/": (2, "left"), "^": (3, "right")})

    def test_production_gets_precedence_of_rightmost_terminal(self):
        g = load_grammar(os.path.join(GRAMMAR_DIR, "ambiguous_expr_prec.txt"))
        self.assertEqual(g.production_precedence(1), (1, "left"))   # E -> E + E
        self.assertEqual(g.production_precedence(2), (2, "left"))   # E -> E * E
        self.assertIsNone(g.production_precedence(3))               # E -> ( E ): ')' has none
        self.assertIsNone(g.production_precedence(4))               # E -> id

    def test_bad_declarations(self):
        with self.assertRaises(ValueError):
            parse_precedence_lines(["%lefty +"])
        with self.assertRaises(ValueError):
            parse_precedence_lines(["%left"])
        with self.assertRaises(ValueError):
            parse_precedence_lines(["%left +", "%right +"])
        with self.assertRaises(ValueError):
            grammar_from_lines(["%left ^", "E -> E + E | id"])   # ^ is not a terminal

    def test_grammar_without_declarations_is_unchanged(self):
        g = load_grammar(os.path.join(GRAMMAR_DIR, "ambiguous_expr.txt"))
        self.assertEqual(g.precedence, {})
        self.assertEqual(build_parsing_table(g, "slr").resolved, [])


class TestResolution(unittest.TestCase):

    def setUp(self):
        self.g = load_grammar(os.path.join(GRAMMAR_DIR, "ambiguous_expr_prec.txt"))

    def test_all_conflicts_resolved_in_every_method(self):
        for method in METHOD_NAMES:
            table = build_parsing_table(self.g, method)
            self.assertEqual(table.conflicts, [], method)
            self.assertGreater(len(table.resolved), 0, method)

    def test_the_four_slr_decisions(self):
        # State 7 = {E -> E + E ·, ...}, state 8 = {E -> E * E ·, ...}
        table = build_parsing_table(self.g, "slr")
        decisions = {(r["state"], r["symbol"]): r["chosen"] for r in table.resolved}
        self.assertEqual(decisions, {(7, "*"): "s5",    # * binds tighter than +: shift
                                     (7, "+"): "r1",    # + is left-associative: reduce
                                     (8, "*"): "r2",    # * is left-associative: reduce
                                     (8, "+"): "r2"})   # E * E binds tighter: reduce

    def test_id_plus_id_times_id(self):
        # The task: the resolved parser builds id + (id * id)
        for method in METHOD_NAMES:
            table, result = parse_with(self.g, "id + id * id", method)
            self.assertTrue(result.accepted, method)
            self.assertEqual(tree_text(result.tree), "(id + (id * id))", method)
            root = result.tree
            self.assertEqual([c.symbol for c in root.children], ["E", "+", "E"])
            self.assertEqual([c.symbol for c in root.children[2].children], ["E", "*", "E"])

    def test_more_trees(self):
        cases = {
            "id * id + id": "((id * id) + id)",
            "id + id + id": "((id + id) + id)",         # left-associative
            "id * id * id": "((id * id) * id)",
            "( id + id ) * id": "((id + id) * id)",
            "id + id * id + id": "((id + (id * id)) + id)",
        }
        for text, expected in cases.items():
            table, result = parse_with(self.g, text)
            self.assertEqual(tree_text(result.tree), expected, text)

    def test_right_associative(self):
        g = grammar_from_lines(["%right ^", "E -> E ^ E | id"])
        table, result = parse_with(g, "id ^ id ^ id")
        self.assertEqual(tree_text(result.tree), "(id ^ (id ^ id))")

    def test_nonassoc_makes_chains_an_error(self):
        g = grammar_from_lines(["%nonassoc <", "E -> E < E | id"])
        table, result = parse_with(g, "id < id")
        self.assertTrue(result.accepted)
        table, result = parse_with(g, "id < id < id")
        self.assertFalse(result.accepted)
        self.assertEqual(result.error_position, 4)          # the second '<'
        self.assertEqual(table.resolved[0]["chosen"], "error")

    def test_without_precedence_default_shift_gives_wrong_tree(self):
        # Yacc's default (always shift) parses id * id + id as id * (id + id)
        g = load_grammar(os.path.join(GRAMMAR_DIR, "ambiguous_expr.txt"))
        table = build_parsing_table(g, "lalr")
        result = parse_text(g, table.action, table.goto_table, "id * id + id",
                            resolve_conflicts=True)
        self.assertEqual(tree_text(result.tree), "(id * (id + id))")

    def test_reduce_reduce_is_not_resolved_by_precedence(self):
        g = grammar_from_lines(["%left a", "S -> A | B", "A -> a", "B -> a"])
        table = build_parsing_table(g, "slr")
        self.assertEqual(len(table.conflicts), 1)
        self.assertEqual(table.resolved, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
