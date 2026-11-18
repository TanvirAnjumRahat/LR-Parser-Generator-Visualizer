"""
main.py - Phase 6: interactive menu for the LR Parser Generator & Visualizer.

Run from the project folder:   python lr_parser/main.py
                         or:   python lr_parser/main.py grammars/expr.txt

Everything the menu does is done by the other modules; this file only asks
the user what to do and calls them:
  grammar.py   - load grammar, FIRST/FOLLOW
  tables.py    - LR(0)/SLR/LALR/CLR tables, conflicts, comparison report
  parser.py    - parse input (full trace or step by step)
  visualize.py - Graphviz drawings
"""

import io
import os
import sys

from grammar import Grammar, load_grammar, print_grammar_info, use_utf8_output
from tables import (ParsingTable, build_parsing_table, print_states, print_table,
                    print_resolutions, explain_conflicts, compare_methods,
                    print_comparison, print_comparison_summary, METHOD_NAMES)
from parser import ParseResult, parse_text, print_result, print_trace_step_by_step

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAMMAR_DIR = os.path.join(PROJECT_DIR, "grammars")

MENU = """
----------------------------------------------------------------
 LR Parser Generator & Visualizer
 Grammar: {grammar}    Method: {method}
----------------------------------------------------------------
  1  Load a grammar
  2  Show grammar, FIRST and FOLLOW sets
  3  Choose method (LR(0), SLR(1), LALR(1), CLR(1))
  4  Show item sets (states of the automaton)
  5  Show parsing table and conflicts
  6  Parse input (full trace)
  7  Parse input step by step
  8  Draw automaton (Graphviz)
  9  Draw parse tree of the last accepted input
 10  Comparison report (all methods)
  0  Exit
"""


class Session:
    """What the user has chosen so far: grammar, method, the table, the last parse."""

    def __init__(self):
        # The type hints say "this starts as None but later holds a Grammar"
        # (otherwise VS Code's type checker thinks they are always None).
        self.grammar: Grammar | None = None
        self.grammar_file: str | None = None
        self.method = "slr"
        self.table: ParsingTable | None = None       # built when first needed
        self.last_result: ParseResult | None = None  # last parse, for drawing its tree

    def get_table(self):
        """The parsing table for the current grammar and method, built only once."""
        if self.table is None:
            self.table = build_parsing_table(self.grammar, self.method)
        return self.table


def ask(read, prompt):
    """Read one answer; end of input (Ctrl+Z / Ctrl+D) counts as 'exit'."""
    try:
        return read(prompt).strip()
    except EOFError:
        return None


def list_grammar_files():
    files = []
    for name in sorted(os.listdir(GRAMMAR_DIR)):
        if name.endswith(".txt"):
            files.append(os.path.join("grammars", name))
    return files


def load_into_session(session, filename):
    """Load a grammar file; on error print the message and keep the old grammar."""
    path = filename
    if not os.path.isabs(path) and not os.path.exists(path):
        path = os.path.join(PROJECT_DIR, filename)     # allow paths relative to the project
    try:
        grammar = load_grammar(path)
    except (OSError, ValueError) as e:
        print(f"Could not load '{filename}': {e}")
        return False
    session.grammar = grammar
    session.grammar_file = filename
    session.table = None
    session.last_result = None
    print(f"Loaded {filename}: {len(grammar.productions) - 1} productions, "
          f"start symbol {grammar.start_symbol}")
    return True


# ---------------------------------------------------------------------
# One function per menu option
# ---------------------------------------------------------------------

def option_load(session, read):
    files = list_grammar_files()
    print("Demo grammars:")
    for n in range(len(files)):
        print(f"  {n + 1:>2}  {files[n]}")
    answer = ask(read, "Number, or a path to a grammar file: ")
    if not answer:
        return
    if answer.isdigit() and 1 <= int(answer) <= len(files):
        load_into_session(session, files[int(answer) - 1])
    else:
        load_into_session(session, answer)


def option_method(session, read):
    methods = list(METHOD_NAMES.keys())
    for n in range(len(methods)):
        print(f"  {n + 1}  {METHOD_NAMES[methods[n]]}")
    answer = ask(read, "Method number: ")
    if answer and answer.isdigit() and 1 <= int(answer) <= len(methods):
        session.method = methods[int(answer) - 1]
        session.table = None
        print(f"Method is now {METHOD_NAMES[session.method]}.")
    else:
        print("Unknown choice; method unchanged.")


def option_states(session):
    print_states(session.grammar, session.get_table())


def option_table(session):
    table = session.get_table()
    print(f"{table.name} parsing table ({len(table.states)} states):")
    print_table(session.grammar, len(table.states), table.action, table.goto_table)
    print()
    print_resolutions(table)
    explain_conflicts(session.grammar, table.conflicts, table.name)


def option_parse(session, read, step_by_step):
    """Options 6 and 7. If the table has conflicts, ask before using Yacc's default choices."""
    table = session.get_table()
    resolve = False
    if table.conflicts:
        print(f"The {table.name} table has {len(table.conflicts)} conflict(s) "
              f"(option 5 explains them).")
        answer = ask(read, "Parse anyway, using Yacc's default choices? (y/n): ")
        if answer is None or answer.lower() != "y":
            return
        resolve = True

    text = ask(read, "Input (e.g. id * id + id): ")
    if text is None:
        return
    result = parse_text(session.grammar, table.action, table.goto_table, text, resolve)
    session.last_result = result
    if result.tokens:
        print("Tokens:", " ".join(repr(t) for t in result.tokens))
        print()

    if step_by_step and result.steps:
        print_trace_step_by_step(result, read)
        print()
        print_result(session.grammar, result, show_trace=False)
    else:
        print_result(session.grammar, result)


def option_draw_automaton(session):
    from visualize import draw_automaton      # needs the graphviz package
    draw_automaton(session.grammar, session.get_table(), session.grammar_file)


def option_draw_tree(session):
    if session.last_result is None or not session.last_result.accepted:
        print("Parse an input that is accepted first (option 6 or 7).")
        return
    from visualize import draw_parse_tree
    draw_parse_tree(session.grammar, session.last_result.tree, session.grammar_file)


def option_compare(session, read):
    answer = ask(read, "Compare [1] the loaded grammar or [2] all demo grammars? ")
    if answer == "2":
        results = []
        for filename in list_grammar_files():
            rows = compare_methods(load_grammar(os.path.join(PROJECT_DIR, filename)))
            results.append((filename, rows))
        print_comparison_summary(results)
    else:
        print_comparison(session.grammar_file, compare_methods(session.grammar))


# ---------------------------------------------------------------------
# The menu loop
# ---------------------------------------------------------------------

def run_menu(read=input, grammar_file=None):
    """
    Show the menu until the user chooses 0 (or input ends).
    'read' is the function that reads one line - input() normally,
    and a scripted function in the tests.
    """
    session = Session()
    if grammar_file:
        load_into_session(session, grammar_file)

    while True:
        grammar_name = session.grammar_file or "(none loaded)"
        print(MENU.format(grammar=grammar_name, method=METHOD_NAMES[session.method]))
        choice = ask(read, "Choose an option: ")
        if choice is None or choice == "0":
            print("Bye.")
            return session
        if choice == "":
            continue                      # just Enter: show the menu again

        if choice == "1":
            option_load(session, read)
            continue
        if choice == "3":
            option_method(session, read)
            continue
        if choice not in ["2", "4", "5", "6", "7", "8", "9", "10"]:
            print(f"'{choice}' is not an option.")
            continue
        if session.grammar is None:
            print("Load a grammar first (option 1).")
            continue

        if choice == "2":
            print_grammar_info(session.grammar)
        elif choice == "4":
            option_states(session)
        elif choice == "5":
            option_table(session)
        elif choice == "6":
            option_parse(session, read, step_by_step=False)
        elif choice == "7":
            option_parse(session, read, step_by_step=True)
        elif choice == "8":
            option_draw_automaton(session)
        elif choice == "9":
            option_draw_tree(session)
        elif choice == "10":
            option_compare(session, read)


if __name__ == "__main__":
    use_utf8_output()
    # "utf-8-sig" drops the invisible BOM that Windows PowerShell puts in front
    # of text piped into a program, so  "6`n..." | python main.py  works too.
    if isinstance(sys.stdin, io.TextIOWrapper):
        sys.stdin.reconfigure(encoding="utf-8-sig")
    start_file = None
    if len(sys.argv) > 1:
        start_file = sys.argv[1]
    run_menu(input, start_file)
