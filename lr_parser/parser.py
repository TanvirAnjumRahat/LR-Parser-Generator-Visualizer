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
from lr0 import canonical_collection
from tables import build_slr_table, find_conflicts, explain_conflicts


class ParseTreeNode:
    """A node of the parse tree: a grammar symbol and its children (left to right)."""

    def __init__(self, symbol, children=None):
        self.symbol = symbol
        if children is None:
            children = []
        self.children = children

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
        self.expected = []       # terminals that would have been valid at the error


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


def parse(grammar, action, goto_table, tokens, resolve_conflicts=False):
    """
    Run Algorithm 4.44 on a list of tokens (terminal names, e.g. ["id", "*", "id"]).
    Works with any ACTION/GOTO table from tables.py.

    If the table has conflicts we refuse to parse, unless resolve_conflicts
    is True; then choose_action() picks one action and the trace says which.
    """
    result = ParseResult()

    conflicts = find_conflicts(action)
    if conflicts and not resolve_conflicts:
        result.error = (f"The parsing table has {len(conflicts)} conflict(s), so the grammar "
                        f"is not deterministic for this table type. Refusing to parse.")
        return result

    input_tokens = list(tokens) + [END_MARKER]
    state_stack = [0]
    node_stack = []      # parse-tree nodes; their symbols are the SYMBOLS column
    ip = 0               # index of the current input token

    while True:
        s = state_stack[-1]
        a = input_tokens[ip]

        # Snapshot of the configuration BEFORE this move (one row of Figure 4.38)
        stack_text = " ".join(str(x) for x in state_stack)
        symbols_text = " ".join(node.symbol for node in node_stack)
        input_text = " ".join(input_tokens[ip:])

        cell = action.get((s, a))

        # ---------- error: empty ACTION entry ----------
        if cell is None:
            result.error_position = ip + 1
            result.expected = expected_terminals(grammar, action, s)
            if a == END_MARKER:
                found = "unexpected end of input"
            elif not grammar.is_terminal(a):
                found = f"'{a}' is not a terminal of this grammar"
            else:
                found = f"unexpected token '{a}'"
            result.error = (f"Syntax error at token {ip + 1}: {found} (in state {s}). "
                            f"Expected one of: {', '.join(result.expected)}")
            result.steps.append((stack_text, symbols_text, input_text, "error"))
            return result

        act, note = choose_action(cell)

        # ---------- shift ----------
        if act.startswith("s"):
            t = int(act[1:])
            state_stack.append(t)
            node_stack.append(ParseTreeNode(a))   # a leaf for the token
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
        print(node.symbol)
        child_prefix = ""
    else:
        if is_last:
            print(prefix + "└── " + node.symbol)
            child_prefix = prefix + "    "
        else:
            print(prefix + "├── " + node.symbol)
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


def print_result(grammar, result):
    """Print the trace, then either the tree + derivation or the error."""
    if result.steps:
        print_trace(result)
        print()

    if not result.accepted:
        print("REJECTED.", result.error)
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
    # Usage: python parser.py <grammar-file> "id * id + id" [--resolve]
    #   --resolve : parse even if the table has conflicts (Yacc default rules)
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    resolve = "--resolve" in args
    if resolve:
        args.remove("--resolve")
    if len(args) < 2:
        print('Usage: python parser.py <grammar-file> "<tokens separated by spaces>" [--resolve]')
        sys.exit(1)

    from visualize import render_parse_tree   # only needed when run as a program

    g = load_grammar(args[0])
    tokens = args[1].split()
    C, trans = canonical_collection(g)
    action, goto_table = build_slr_table(g, C, trans)

    print(f"Grammar: {args[0]}   Table: SLR(1)   Input: {' '.join(tokens)}")
    print()

    conflicts = find_conflicts(action)
    if conflicts:
        print("WARNING: the SLR(1) table has conflicts.")
        explain_conflicts(g, conflicts)
        print()

    result = parse(g, action, goto_table, tokens, resolve_conflicts=resolve)
    print_result(g, result)
    if not result.accepted and conflicts and not resolve:
        print("(Run again with --resolve to parse using Yacc's default conflict rules.)")

    if result.accepted:
        print()
        render_parse_tree(g, result.tree, "parse_tree")
