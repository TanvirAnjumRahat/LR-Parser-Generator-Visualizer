"""
Phase 6 tests: the interactive menu (main.py) and step-by-step parsing.
The menu reads its answers through a function, so the tests give it a
scripted list of answers instead of typing them.

Run from the project folder:   python tests/test_main.py
"""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "lr_parser"))

from main import run_menu, list_grammar_files
from grammar import load_grammar
from tables import build_parsing_table
from parser import parse_text, print_trace_step_by_step

GRAMMAR_DIR = os.path.join(PROJECT_DIR, "grammars")


def scripted(answers):
    """A replacement for input(): returns the answers one by one, then acts like Ctrl+Z."""
    remaining = list(answers)

    def read(_prompt=""):            # the prompt is ignored, like a user who never reads it
        if not remaining:
            raise EOFError
        return remaining.pop(0)
    return read


def run(answers, grammar_file=None):
    output = io.StringIO()
    with redirect_stdout(output):
        session = run_menu(scripted(answers), grammar_file)
    return session, output.getvalue()


def last_result(session):
    """The last ParseResult. The assert also tells VS Code's type checker it is not None."""
    assert session.last_result is not None, "nothing was parsed"
    return session.last_result


class TestMenu(unittest.TestCase):

    def test_load_by_number(self):
        files = list_grammar_files()
        number = str(files.index(os.path.join("grammars", "expr.txt")) + 1)
        session, out = run(["1", number, "0"])
        assert session.grammar is not None
        self.assertEqual(session.grammar.start_symbol, "E")
        self.assertIn("Loaded", out)
        self.assertIn("Bye.", out)

    def test_needs_a_grammar_first(self):
        session, out = run(["5", "0"])
        self.assertIn("Load a grammar first", out)

    def test_bad_grammar_path(self):
        session, out = run(["1", "no_such_file.txt", "0"])
        self.assertIn("Could not load", out)
        self.assertIsNone(session.grammar)

    def test_first_follow_states_and_table(self):
        session, out = run(["2", "4", "5", "0"], "grammars/expr.txt")
        self.assertIn("FOLLOW(T)  = { +, *, ), $ }", out)
        self.assertIn("Canonical collection of LR(0) items: 12 states", out)
        self.assertIn("No conflicts: the grammar is SLR(1).", out)

    def test_choose_method(self):
        session, out = run(["3", "4", "5", "0"], "grammars/cc.txt")   # 4 = CLR(1)
        self.assertEqual(session.method, "clr")
        self.assertIn("CLR(1) parsing table (10 states)", out)

    def test_lr0_method_shows_conflicts(self):
        session, out = run(["3", "1", "5", "0"], "grammars/expr.txt")
        self.assertIn("NOT LR(0)", out)

    def test_parse(self):
        session, out = run(["6", "count + 10 * (x + y)", "0"], "grammars/expr_num.txt")
        self.assertTrue(last_result(session).accepted)
        self.assertIn("id (count)", out)

    def test_parse_with_conflicts_asks_first(self):
        session, out = run(["6", "n", "0"], "grammars/ambiguous_expr.txt")
        self.assertIn("The SLR(1) table has 4 conflict(s)", out)
        self.assertIsNone(session.last_result)          # answered 'n': nothing parsed
        session, out = run(["6", "y", "id + id", "0"], "grammars/ambiguous_expr.txt")
        self.assertTrue(last_result(session).accepted)

    def test_step_by_step_from_menu(self):
        # Enter, Enter, then 'r' runs to the end
        session, out = run(["7", "id * id + id", "", "", "r", "0"], "grammars/expr.txt")
        self.assertTrue(last_result(session).accepted)
        self.assertIn("ACTION[0, id] = s5", out)
        self.assertIn("GOTO[0, F] = 3", out)
        self.assertIn("ACCEPTED.", out)

    def test_comparison_of_loaded_grammar(self):
        session, out = run(["10", "1", "0"], "grammars/slr_conflict.txt")
        self.assertIn("=> The grammar is LALR(1)", out)

    def test_comparison_of_all_grammars(self):
        session, out = run(["10", "2", "0"], "grammars/expr.txt")
        for name in ["cc.txt", "dangling_else.txt", "ambiguous_expr_prec.txt"]:
            self.assertIn(name, out)

    def test_draw_tree_needs_a_parse(self):
        session, out = run(["9", "0"], "grammars/expr.txt")
        self.assertIn("Parse an input that is accepted first", out)

    def test_unknown_option_and_end_of_input(self):
        session, out = run(["42"], "grammars/expr.txt")    # then input ends
        self.assertIn("'42' is not an option", out)
        self.assertIn("Bye.", out)


class TestStepByStep(unittest.TestCase):

    def setUp(self):
        g = load_grammar(os.path.join(GRAMMAR_DIR, "expr.txt"))
        table = build_parsing_table(g, "slr")
        self.result = parse_text(g, table.action, table.goto_table, "id * id + id")

    def test_one_explanation_per_move(self):
        self.assertEqual(len(self.result.explanations), len(self.result.steps))
        self.assertEqual(self.result.explanations[6],
                         "ACTION[10, +] = r3: pop 3 symbol(s) 'T * F' (the handle), "
                         "state 0 is now on top, GOTO[0, T] = 2: push 'T' and state 2.")
        self.assertIn("acc", self.result.explanations[-1])

    def test_waits_for_enter_between_moves(self):
        prompts = []

        def read(prompt=""):
            prompts.append(prompt)
            return ""
        with redirect_stdout(io.StringIO()):
            finished = print_trace_step_by_step(self.result, read)
        self.assertTrue(finished)
        self.assertEqual(len(prompts), len(self.result.steps) - 1)   # no wait after the last

    def test_quit_early(self):
        output = io.StringIO()
        with redirect_stdout(output):
            finished = print_trace_step_by_step(self.result, scripted(["", "q"]))
        # move 1, Enter, move 2, q: stop before move 3
        self.assertFalse(finished)
        self.assertIn("(2)", output.getvalue())
        self.assertNotIn("(3)", output.getvalue())

    def test_epsilon_reduce_explanation(self):
        g = load_grammar(os.path.join(GRAMMAR_DIR, "epsilon.txt"))
        table = build_parsing_table(g, "slr")
        result = parse_text(g, table.action, table.goto_table, "id")
        self.assertIn("pop nothing (epsilon rule)", " ".join(result.explanations))


if __name__ == "__main__":
    unittest.main(verbosity=2)
