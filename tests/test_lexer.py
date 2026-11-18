"""
Tests for lexer.py and for parsing raw text through the lexer (parse_text).

Run from the project folder:   python tests/test_lexer.py
"""

import os
import sys
import unittest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "lr_parser"))

from lexer import tokenize, LexicalError
from grammar import load_grammar
from lr0 import canonical_collection
from tables import build_slr_table
from parser import parse_text

GRAMMAR_DIR = os.path.join(PROJECT_DIR, "grammars")


def kinds(tokens):
    return [t.kind for t in tokens]


def lexemes(tokens):
    return [t.lexeme for t in tokens]


class TestTokenize(unittest.TestCase):

    def test_example_from_phase_plan(self):
        tokens = tokenize("count + 10 * (x + y)")
        self.assertEqual(kinds(tokens), ["id", "+", "num", "*", "(", "id", "+", "id", ")"])
        self.assertEqual(lexemes(tokens), ["count", "+", "10", "*", "(", "x", "+", "y", ")"])

    def test_columns(self):
        tokens = tokenize("count + 10 * (x + y)")
        self.assertEqual([t.column for t in tokens], [1, 7, 9, 12, 14, 15, 17, 19, 20])

    def test_line_and_column_over_several_lines(self):
        tokens = tokenize("a +\n  b2 *\n\tc")
        positions = [(t.lexeme, t.line, t.column) for t in tokens]
        self.assertEqual(positions, [("a", 1, 1), ("+", 1, 3), ("b2", 2, 3),
                                     ("*", 2, 6), ("c", 3, 2)])

    def test_no_spaces_needed(self):
        self.assertEqual(kinds(tokenize("a+b*(c)")), ["id", "+", "id", "*", "(", "id", ")"])

    def test_numbers(self):
        tokens = tokenize("7 3.14 6E23 1E-5")
        self.assertEqual(kinds(tokens), ["num", "num", "num", "num"])
        self.assertEqual(lexemes(tokens), ["7", "3.14", "6E23", "1E-5"])

    def test_identifier_with_digits_and_underscore(self):
        tokens = tokenize("_tmp1 x2y")
        self.assertEqual(lexemes(tokens), ["_tmp1", "x2y"])

    def test_operators_use_the_lexeme_as_kind(self):
        self.assertEqual(kinds(tokenize("x <= y == z != w = v < u > t >= s && r || !q")),
                         ["id", "<=", "id", "==", "id", "!=", "id", "=", "id", "<", "id",
                          ">", "id", ">=", "id", "&&", "id", "||", "!", "id"])

    def test_reserved_words_from_grammar(self):
        tokens = tokenize("if x then y", keywords={"if", "then"})
        self.assertEqual(kinds(tokens), ["if", "id", "then", "id"])

    def test_comments_are_skipped(self):
        tokens = tokenize("a /* note */ + b // rest of line\n* c")
        self.assertEqual(lexemes(tokens), ["a", "+", "b", "*", "c"])

    def test_empty_input(self):
        self.assertEqual(tokenize("   \n  "), [])


class TestLexicalErrors(unittest.TestCase):

    def check_error(self, text, line, column, words):
        with self.assertRaises(LexicalError) as caught:
            tokenize(text)
        self.assertEqual((caught.exception.line, caught.exception.column), (line, column))
        self.assertIn(words, str(caught.exception))

    def test_unknown_character(self):
        self.check_error("x + @", 1, 5, "unexpected character '@'")

    def test_error_on_second_line(self):
        self.check_error("x +\ny # z", 2, 3, "'#'")

    def test_single_ampersand(self):
        self.check_error("a & b", 1, 3, "'&'")

    def test_malformed_number(self):
        self.check_error("3.", 1, 1, "malformed number")

    def test_unclosed_comment(self):
        self.check_error("a /* oops", 1, 3, "never closed")


class TestParseText(unittest.TestCase):
    """Lexer + parser together."""

    def build(self, filename):
        g = load_grammar(os.path.join(GRAMMAR_DIR, filename))
        states, transitions = canonical_collection(g)
        action, goto_table = build_slr_table(g, states, transitions)
        return g, action, goto_table

    def test_real_expression_accepted(self):
        g, action, goto_table = self.build("expr_num.txt")
        result = parse_text(g, action, goto_table, "count + 10 * (x + y)")
        self.assertTrue(result.accepted, result.error)
        self.assertEqual(result.tree.leaves(), ["id", "+", "num", "*", "(", "id", "+", "id", ")"])

    def test_tree_leaves_keep_lexemes(self):
        g, action, goto_table = self.build("expr_num.txt")
        result = parse_text(g, action, goto_table, "count + 10")
        labels = []
        node = result.tree
        # E -> E + T : collect the leaf labels left to right
        stack = [node]
        while stack:
            n = stack.pop()
            if not n.children:
                labels.append(n.label())
            for child in reversed(n.children):
                stack.append(child)
        self.assertEqual(labels, ["id (count)", "+", "num (10)"])

    def test_token_kind_not_in_grammar(self):
        g, action, goto_table = self.build("expr.txt")     # has no "num"
        result = parse_text(g, action, goto_table, "count + 10")
        self.assertFalse(result.accepted)
        self.assertEqual(result.error_position, 3)
        self.assertIn("'num'", result.error)
        self.assertIn("line 1, column 9", result.error)

    def test_lexical_error_is_reported(self):
        g, action, goto_table = self.build("expr_num.txt")
        result = parse_text(g, action, goto_table, "x + @y")
        self.assertFalse(result.accepted)
        self.assertIn("Lexical error at line 1, column 5", result.error)

    def test_syntax_error_has_line_and_column(self):
        g, action, goto_table = self.build("expr_num.txt")
        result = parse_text(g, action, goto_table, "x +\n  * y")
        self.assertFalse(result.accepted)
        self.assertEqual((result.error_token.line, result.error_token.column), (2, 3))
        self.assertIn("line 2, column 3", result.error)

    def test_word_terminal_of_grammar(self):
        # reduce_reduce.txt has the terminal "a": the lexer must not turn it into "id"
        g, action, goto_table = self.build("reduce_reduce.txt")
        result = parse_text(g, action, goto_table, "a", resolve_conflicts=True)
        self.assertTrue(result.accepted, result.error)

    def test_old_token_style_input_still_works(self):
        g, action, goto_table = self.build("expr.txt")
        result = parse_text(g, action, goto_table, "id * id + id")
        self.assertTrue(result.accepted)
        self.assertEqual(len(result.steps), 14)     # Figure 4.38


if __name__ == "__main__":
    unittest.main(verbosity=2)
