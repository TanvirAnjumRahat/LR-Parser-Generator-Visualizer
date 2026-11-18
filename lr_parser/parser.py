"""
parser.py - Phase 3: table-driven LR parsing with trace, parse tree and errors.

Follows Dragon Book Algorithm 4.44 ("LR-parsing algorithm"):

  let a be the first symbol of w$;
  while (1) {
      let s be the state on top of the stack;
      if ACTION[s, a] = shift t:
          push t onto the stack; let a be the next input symbol;
      else if ACTION[s, a] = reduce A -> beta:
          pop |beta| symbols off the stack;
          let t be the state now on top of the stack;
          push GOTO[t, A] onto the stack;
          output the production A -> beta;
      else if ACTION[s, a] = accept: parsing is done;
      else: call error-recovery routine;
  }

The parser only looks at the ACTION and GOTO tables. It does not know or
care whether they were built by SLR, CLR or LALR - so the same code will
be reused for every table type.

Besides the state stack we keep a stack of parse-tree nodes. Its symbols
are the "SYMBOLS" column of Figure 4.38, and every reduce builds a new
tree node A whose children are the |beta| nodes popped off. When we accept,
the single node left is the root of the parse tree.
"""

import sys
from grammar import load_grammar, END_MARKER, EPSILON
from tables import (find_conflicts, explain_conflicts,
                    build_parsing_table, pop_option, METHOD_NAMES)
from lexer import Token, tokenize, LexicalError, print_tokens


class ParseTreeNode:
    """
    A node of the parse tree: a grammar symbol and its children (left to right).
    Leaves made from input tokens also keep the lexeme, e.g. symbol "id",
    lexeme "count".
    """

    def __init__(self, symbol, children=None, lexeme=None):
        self.symbol = symbol
        if children is None:
            children = []
        self.children = children
        self.lexeme = lexeme

    def label(self):
        """Text to show for this node: "id (count)", or just the symbol."""
        if self.lexeme is not None and self.lexeme != self.symbol:
            return f"{self.symbol} ({self.lexeme})"
        return self.symbol

    def leaves(self):
        """The yield of the tree: its leaves from left to right."""
        if not self.children:
            return [self.symbol]
        result = []
        for child in self.children:
            result.extend(child.leaves())
        return result


class ParseResult:
    """Everything the parser found out, so printing and testing are separate from parsing."""

    def __init__(self):
        self.accepted = False
        self.steps = []          # list of (stack, symbols, input, action) strings, one per move
        self.reductions = []     # production numbers in the order they were reduced
        self.tree = None         # root ParseTreeNode if accepted
        self.error = None        # error message if not accepted
        self.error_position = None   # 1-based token position of the error
        self.error_token = None      # the Token where the error happened (has line/column)
        self.expected = []       # terminals that would have been valid at the error
        self.tokens = []         # the tokens that were parsed


def choose_action(cell):
    """
    Pick the action to perform from an ACTION cell.

    Normally the cell holds exactly one action. If it holds more (a conflict)
    and the user asked us to go on anyway, we use the same default rules as
    Yacc (Dragon Book Section 4.9.2):
      - shift-reduce conflict  : prefer the SHIFT
      - reduce-reduce conflict : prefer the production listed first in the grammar
    Returns (action, note) where note explains the choice ("" if no conflict).
    """
    actions = list(cell.keys())
    if len(actions) == 1:
        return actions[0], ""

    for act in actions:
        if act.startswith("s"):
            return act, f"conflict {'/'.join(actions)}: chose {act} (prefer shift)"

    # Only reduces (and maybe accept, which is reducing by production 0)
    best = None
    best_number = None
    for act in actions:
        if act == "acc":
            number = 0
        else:
            number = int(act[1:])
        if best is None or number < best_number:
            best = act
            best_number = number
    return best, f"conflict {'/'.join(actions)}: chose {best} (earliest production)"


def expected_terminals(grammar, action, state):
    """Terminals that have an entry in ACTION[state, *] - what the parser could accept here."""
    expected = []
    for a in grammar.terminals + [END_MARKER]:
        if (state, a) in action:
            expected.append(a)
    return expected


def make_token_list(tokens):
    """
    Accept either Token objects (from the lexer) or plain terminal names
    like ["id", "*", "id"], and return a list of Token objects.
    Plain names get position line 1, column = token number.
    """
    result = []
    number = 0
    for t in tokens:
        number += 1
        if isinstance(t, Token):
            result.append(t)
        else:
            result.append(Token(t, t, 1, number))
    return result


def end_marker_token(tokens):
    """The $ token, placed just after the last real token."""
    if not tokens:
        return Token(END_MARKER, END_MARKER, 1, 1)
    last = tokens[-1]
    return Token(END_MARKER, END_MARKER, last.line, last.column + len(last.lexeme))


def where(token):
    return f"line {token.line}, column {token.column}"


def parse(grammar, action, goto_table, tokens, resolve_conflicts=False):
    """
    Run Algorithm 4.44 on a list of tokens: Token objects from the lexer, or
    plain terminal names like ["id", "*", "id"].
    Works with any ACTION/GOTO table from tables.py.

    If the table has conflicts we refuse to parse, unless resolve_conflicts
    is True; then choose_action() picks one action and the trace says which.
    """
    result = ParseResult()
    tokens = make_token_list(tokens)
    result.tokens = tokens

    conflicts = find_conflicts(action)
    if conflicts and not resolve_conflicts:
        result.error = (f"The parsing table has {len(conflicts)} conflict(s), so the grammar "
                        f"is not deterministic for this table type. Refusing to parse.")
        return result

    # Every token kind must be a terminal of the grammar, otherwise the
    # parser could never shift it. Check this before parsing for a clear message.
    for n in range(len(tokens)):
        t = tokens[n]
        if t.kind not in grammar.terminals:
            result.error_position = n + 1
            result.error_token = t
            result.error = (f"Token {n + 1} '{t.lexeme}' at {where(t)} has kind '{t.kind}', "
                            f"which is not a terminal of this grammar. "
                            f"Terminals are: {', '.join(grammar.terminals)}")
            return result

    input_tokens = tokens + [end_marker_token(tokens)]
    state_stack = [0]
    node_stack = []      # parse-tree nodes; their symbols are the SYMBOLS column
    ip = 0               # index of the current input token

    while True:
        s = state_stack[-1]
        a = input_tokens[ip].kind

        # Snapshot of the configuration BEFORE this move (one row of Figure 4.38)
        stack_text = " ".join(str(x) for x in state_stack)
        symbols_text = " ".join(node.symbol for node in node_stack)
        input_text = " ".join(t.kind for t in input_tokens[ip:])

        cell = action.get((s, a))

        # ---------- error: empty ACTION entry ----------
        if cell is None:
            bad = input_tokens[ip]
            result.error_position = ip + 1
            result.error_token = bad
            result.expected = expected_terminals(grammar, action, s)
            if a == END_MARKER:
                found = "unexpected end of input"
            elif bad.lexeme == a:
                found = f"unexpected token '{a}'"
            else:
                found = f"unexpected token '{bad.lexeme}' ({a})"
            result.error = (f"Syntax error at {where(bad)} (token {ip + 1}): {found}, "
                            f"in state {s}. Expected one of: {', '.join(result.expected)}")
            result.steps.append((stack_text, symbols_text, input_text, "error"))
            return result

        act, note = choose_action(cell)

        # ---------- shift ----------
        if act.startswith("s"):
            t = int(act[1:])
            state_stack.append(t)
            # A leaf for the token; it keeps the lexeme, e.g. id (count)
            node_stack.append(ParseTreeNode(a, lexeme=input_tokens[ip].lexeme))
            ip += 1
            description = "shift"

        # ---------- reduce by A -> beta ----------
        elif act.startswith("r"):
            prod_index = int(act[1:])
            A, beta = grammar.productions[prod_index]

            # Pop |beta| states and |beta| tree nodes. We pop one at a time
            # instead of slicing with [-k:], because for an epsilon rule k = 0
            # and list[-0:] would return the WHOLE list.
            children = []
            for _ in range(len(beta)):
                state_stack.pop()
                children.insert(0, node_stack.pop())  # insert at front keeps left-to-right order

            if len(beta) == 0:
                children = [ParseTreeNode(EPSILON)]   # show A -> epsilon in the tree

            t = state_stack[-1]
            state_stack.append(goto_table[(t, A)])
            node_stack.append(ParseTreeNode(A, children))
            result.reductions.append(prod_index)
            description = f"reduce by {grammar.production_to_string(prod_index)}"

        # ---------- accept ----------
        else:
            result.steps.append((stack_text, symbols_text, input_text, "accept"))
            result.accepted = True
            result.tree = node_stack[-1]
            return result

        if note:
            description += f"   [{note}]"
        result.steps.append((stack_text, symbols_text, input_text, description))


def parse_text(grammar, action, goto_table, text, resolve_conflicts=False):
    """
    Parse raw source text: run the lexer first, then the LR parser.
    The grammar's terminals are passed to the lexer as reserved words.
    A lexical error is returned as a failed ParseResult.
    """
    try:
        tokens = tokenize(text, keywords=set(grammar.terminals))
    except LexicalError as e:
        result = ParseResult()
        result.error = str(e)
        return result
    return parse(grammar, action, goto_table, tokens, resolve_conflicts)


def rightmost_derivation(grammar, reductions):
    """
    Bottom-up parsing traces out a rightmost derivation in REVERSE
    (Dragon Book Section 4.5). So we start from the start symbol and apply
    the reductions from last to first, each time replacing the RIGHTMOST
    non-terminal. Returns the list of sentential forms.
    """
    form = [grammar.start_symbol]
    forms = [form]
    for prod_index in reversed(reductions):
        lhs, rhs = grammar.productions[prod_index]

        # Find the rightmost non-terminal in the current sentential form
        pos = len(form) - 1
        while pos >= 0 and not grammar.is_non_terminal(form[pos]):
            pos -= 1

        form = form[:pos] + rhs + form[pos + 1:]
        forms.append(form)
    return forms


# ----------------------------------------------------------------------
# Printing
# ----------------------------------------------------------------------

def print_trace(result):
    """Print the moves in the layout of Dragon Book Figure 4.38."""
    headers = ("", "STACK", "SYMBOLS", "INPUT", "ACTION")
    rows = []
    for n in range(len(result.steps)):
        stack_text, symbols_text, input_text, action_text = result.steps[n]
        rows.append((f"({n + 1})", stack_text, symbols_text, input_text, action_text))

    widths = []
    for col in range(4):
        width = len(headers[col])
        for row in rows:
            width = max(width, len(row[col]))
        widths.append(width)

    def format_row(row):
        return (row[0].rjust(widths[0]) + "  " +
                row[1].ljust(widths[1]) + "  " +
                row[2].ljust(widths[2]) + "  " +
                row[3].rjust(widths[3]) + "  " +   # input is right-aligned, as in the book
                row[4])

    print(format_row(headers))
    print("-" * (sum(widths) + 8 + 30))
    for row in rows:
        print(format_row(row))


def print_tree(node, prefix="", is_last=True, is_root=True):
    """Print the parse tree sideways in the console."""
    if is_root:
        print(node.label())
        child_prefix = ""
    else:
        if is_last:
            print(prefix + "└── " + node.label())
            child_prefix = prefix + "    "
        else:
            print(prefix + "├── " + node.label())
            child_prefix = prefix + "│   "

    for i in range(len(node.children)):
        last = (i == len(node.children) - 1)
        print_tree(node.children[i], child_prefix, last, False)


def form_to_string(form):
    if len(form) == 0:
        return EPSILON
    return " ".join(form)


def print_derivation(forms):
    print("    " + form_to_string(forms[0]))
    for form in forms[1:]:
        print(" =>rm " + form_to_string(form))


def reductions_before_error(result):
    """
    How many reduce moves the parser made after its last shift, before it
    found the error. All LR parsers detect the error at the same token, but
    SLR and LALR may first do some useless reductions; canonical LR does not
    (its lookaheads are exact), so it reports the error sooner.
    """
    count = 0
    for stack, symbols, remaining, action_text in reversed(result.steps):
        if action_text.startswith("reduce"):
            count += 1
        elif action_text.startswith("shift"):
            break
    return count


def print_result(grammar, result):
    """Print the trace, then either the tree + derivation or the error."""
    if result.steps:
        print_trace(result)
        print()

    if not result.accepted:
        print("REJECTED.", result.error)
        if result.steps:
            print(f"Reductions done before the error was detected: {reductions_before_error(result)}")
        return

    print("ACCEPTED.")
    print()
    print("Productions used (in the order they were reduced):")
    for prod_index in result.reductions:
        print(f"  ({prod_index}) {grammar.production_to_string(prod_index)}")
    print()
    print("Rightmost derivation (the reductions in reverse order):")
    print_derivation(rightmost_derivation(grammar, result.reductions))
    print()
    print("Parse tree:")
    print_tree(result.tree)


if __name__ == "__main__":
    # Usage: python parser.py <grammar-file> "<source text>"
    #                         [--method slr|clr|lalr] [--resolve] [--out NAME]
    #   the text goes through the lexer: "count + 10 * (x + y)" -> id + num * ( id + id )
    #   --method  : which parsing table to use (default slr)
    #   --resolve : parse even if the table has conflicts (Yacc default rules)
    #   --out NAME: name output files NAME_parse_tree.png (default: grammar file name)
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    resolve = "--resolve" in args
    if resolve:
        args.remove("--resolve")
    out = pop_option(args, "--out")
    method = pop_option(args, "--method", "slr")
    if len(args) < 2 or method not in METHOD_NAMES:
        print('Usage: python parser.py <grammar-file> "<source text>" '
              '[--method slr|clr|lalr] [--resolve] [--out NAME]')
        sys.exit(1)

    # visualize needs the graphviz package, so import it only when run as a program
    from visualize import parse_tree_graph, save_graph, output_base_name

    g = load_grammar(args[0])
    table = build_parsing_table(g, method)
    action = table.action
    goto_table = table.goto_table

    print(f"Grammar: {args[0]}   Table: {table.name} ({len(table.states)} states)   "
          f"Input: {args[1]}")
    print()

    conflicts = table.conflicts
    if conflicts:
        print(f"WARNING: the {table.name} table has conflicts.")
        explain_conflicts(g, conflicts, table.name)
        print()

    result = parse_text(g, action, goto_table, args[1], resolve_conflicts=resolve)
    if result.tokens:
        print("Tokens from the lexer:")
        print_tokens(result.tokens)
        print()
    print_result(g, result)
    if not result.accepted and conflicts and not resolve:
        print("(Run again with --resolve to parse using Yacc's default conflict rules.)")

    if result.accepted:
        print()
        save_graph(parse_tree_graph(g, result.tree), output_base_name(args[0], out) + "_parse_tree")
