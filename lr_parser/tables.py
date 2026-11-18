"""
tables.py - Phase 2: SLR(1) parsing table (ACTION / GOTO) with conflict detection.

Based on build_slr_table() in labs/4.6-slr_parser.py, following
Dragon Book Algorithm 4.46 ("Constructing an SLR-parsing table"):

  For each state i (built from item set I_i):
   (a) If  A -> alpha · a beta  is in I_i, a is a terminal, and GOTO(I_i, a) = I_j,
       set ACTION[i, a] = "shift j".
   (b) If  A -> alpha ·  is in I_i (A is not S'), then for every a in FOLLOW(A),
       set ACTION[i, a] = "reduce A -> alpha".
   (c) If  S' -> S ·  is in I_i, set ACTION[i, $] = "accept".
   GOTO[i, A] = j  if GOTO(I_i, A) = I_j for a non-terminal A.

  If any ACTION cell gets two different actions, the grammar is not SLR(1).
  Instead of silently overwriting (as the old lab code did), every cell keeps
  ALL its candidate actions together with the item that caused each one, so
  we can explain every conflict.

Action strings use Dragon Book notation:  s5 = shift to state 5,
r2 = reduce by production (2),  acc = accept.
"""

import sys
from grammar import load_grammar, print_grammar_info, END_MARKER
from lr0 import canonical_collection, print_collection


def add_action(action, state, symbol, act, item, reason):
    """
    Record that 'act' (e.g. "s5" or "r2") belongs in ACTION[state, symbol].

    action[(state, symbol)] is a dict:  act -> list of (item, reason)
    So a cell with one key is fine; a cell with two or more keys is a conflict.
    """
    key = (state, symbol)
    if key not in action:
        action[key] = {}
    cell = action[key]
    if act not in cell:
        cell[act] = []
    cell[act].append((item, reason))


def build_slr_table(grammar, states, transitions):
    """Algorithm 4.46. Returns (action, goto_table)."""
    action = {}
    goto_table = {}

    for i in range(len(states)):
        for item in states[i]:
            a = item.next_symbol()

            if a is not None and grammar.is_terminal(a):
                # Rule (a): shift
                j = transitions[(i, a)]
                add_action(action, i, a, f"s{j}", item, f"GOTO(I{i}, {a}) = I{j}")

            elif item.is_complete():
                if item.lhs == grammar.augmented_start:
                    # Rule (c): accept
                    add_action(action, i, END_MARKER, "acc", item, "S' -> S · means the whole input is S")
                else:
                    # Rule (b): reduce on every terminal in FOLLOW(lhs).
                    # We use item.prod_index directly - no searching (epsilon fix).
                    for a in grammar.follow[item.lhs]:
                        add_action(action, i, a, f"r{item.prod_index}", item,
                                   f"'{a}' is in FOLLOW({item.lhs})")

        # GOTO part of the table: transitions on non-terminals
        for A in grammar.non_terminals[1:]:
            if (i, A) in transitions:
                goto_table[(i, A)] = transitions[(i, A)]

    return action, goto_table


def find_conflicts(action):
    """
    Return a list of conflicts, one per ACTION cell that has 2+ actions.
    Each conflict is a dict: state, symbol, kind, cell.
      shift-reduce  : the cell has a shift and at least one reduce
      reduce-reduce : the cell has two or more reduces (accept counts as
                      reducing by S' -> S)
    """
    conflicts = []
    for (state, symbol) in sorted(action.keys(), key=lambda k: (k[0], str(k[1]))):
        cell = action[(state, symbol)]
        if len(cell) < 2:
            continue

        shift_count = 0
        reduce_count = 0
        for act in cell:
            if act.startswith("s"):
                shift_count += 1
            else:
                reduce_count += 1

        kinds = []
        if shift_count > 0 and reduce_count > 0:
            kinds.append("shift-reduce")
        if reduce_count > 1:
            kinds.append("reduce-reduce")

        conflicts.append({
            "state": state,
            "symbol": symbol,
            "kind": " and ".join(kinds),
            "cell": cell,
        })
    return conflicts


def explain_conflicts(grammar, conflicts, table_name="SLR(1)"):
    """Print a plain-English explanation of every conflict."""
    if not conflicts:
        print(f"No conflicts: the grammar is {table_name}.")
        return

    print(f"{len(conflicts)} conflict(s) found: the grammar is NOT {table_name}.")
    number = 0
    for c in conflicts:
        number += 1
        print()
        print(f"Conflict {number}: {c['kind'].upper()} conflict in state {c['state']} "
              f"on input '{c['symbol']}'")
        for act, causes in c["cell"].items():
            if act.startswith("s"):
                what = f"shift to state {act[1:]}"
            elif act == "acc":
                what = "accept"
            else:
                what = f"reduce by ({act[1:]}) {grammar.production_to_string(int(act[1:]))}"
            print(f"    {act:<4} {what}")
            for item, reason in causes:
                print(f"           because of item  [{item}]   ({reason})")


def print_table(grammar, num_states, action, goto_table):
    """Print ACTION and GOTO as one aligned grid, like Dragon Book Figure 4.37."""
    terminal_cols = grammar.terminals + [END_MARKER]
    nonterminal_cols = grammar.non_terminals[1:]     # no column for S'

    # Text of every cell; conflicting cells show all actions, e.g. "s6/r5"
    def action_text(i, a):
        cell = action.get((i, a))
        if cell is None:
            return ""
        return "/".join(cell.keys())

    def goto_text(i, A):
        if (i, A) in goto_table:
            return str(goto_table[(i, A)])
        return ""

    # Column width = widest entry in that column (at least 3)
    def column_width(header, texts):
        width = max(3, len(header))
        for t in texts:
            width = max(width, len(t))
        return width

    t_widths = []
    for a in terminal_cols:
        t_widths.append(column_width(a, [action_text(i, a) for i in range(num_states)]))
    n_widths = []
    for A in nonterminal_cols:
        n_widths.append(column_width(A, [goto_text(i, A) for i in range(num_states)]))

    state_width = max(5, len(str(num_states - 1)))

    # Total width of the ACTION and GOTO blocks (each column is " x |")
    action_block = sum(w + 3 for w in t_widths) - 1
    goto_block = sum(w + 3 for w in n_widths) - 1

    # Header line 1: ACTION / GOTO titles
    print(" " * state_width + " |" + "ACTION".center(action_block) + "|" + "GOTO".center(goto_block))

    # Header line 2: symbol names
    line = "State".rjust(state_width) + " |"
    for a, w in zip(terminal_cols, t_widths):
        line += " " + a.center(w) + " |"
    for A, w in zip(nonterminal_cols, n_widths):
        line += " " + A.center(w) + " |"
    print(line)

    # Separator
    sep = "-" * state_width + "-+"
    for w in t_widths + n_widths:
        sep += "-" * (w + 2) + "+"
    print(sep)

    # One row per state
    for i in range(num_states):
        line = str(i).rjust(state_width) + " |"
        for a, w in zip(terminal_cols, t_widths):
            line += " " + action_text(i, a).center(w) + " |"
        for A, w in zip(nonterminal_cols, n_widths):
            line += " " + goto_text(i, A).center(w) + " |"
        print(line)


if __name__ == "__main__":
    # Usage: python tables.py ../grammars/expr.txt
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print("Usage: python tables.py <grammar-file> [more files...]")
        sys.exit(1)

    for filename in sys.argv[1:]:
        print("=" * 70)
        print("Grammar file:", filename)
        print("=" * 70)
        g = load_grammar(filename)
        print_grammar_info(g)
        print()

        C, trans = canonical_collection(g)
        print_collection(g, C, trans)
        print()

        action, goto_table = build_slr_table(g, C, trans)
        print("SLR(1) parsing table:")
        print_table(g, len(C), action, goto_table)
        print()
        explain_conflicts(g, find_conflicts(action))
        print()
