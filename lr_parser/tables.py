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

Later phases add, in this same file:
  - LR(0) tables (Phase 6): reduce on EVERY terminal
  - CLR(1) and LALR(1) tables (Phase 5): reduce on the item's lookahead
  - precedence/associativity resolution of conflicts, as Yacc does (Phase 6)
  - a comparison report of all four methods for one grammar (Phase 6)
"""

import sys
from grammar import load_grammar, print_grammar_info, END_MARKER, use_utf8_output
from lr0 import canonical_collection, print_collection
from lr1 import (canonical_lr1_collection, merge_lalr_states,
                 print_lr1_collection, print_merge_report)

# The four table types this project builds, from weakest to strongest,
# and their display names.
METHOD_NAMES = {"lr0": "LR(0)", "slr": "SLR(1)", "lalr": "LALR(1)", "clr": "CLR(1)"}


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


def build_lr0_table(grammar, states, transitions):
    """
    LR(0) table: the same as SLR, except rule (b) reduces on EVERY terminal
    (and $), because an LR(0) parser decides to reduce without looking at
    the next input symbol at all. So any state that has a complete item
    together with another item (a shift, or another complete item) is a
    conflict. A grammar is LR(0) if this table has no conflicts.
    """
    action = {}
    goto_table = {}
    all_terminals = grammar.terminals + [END_MARKER]

    for i in range(len(states)):
        for item in states[i]:
            a = item.next_symbol()

            if a is not None and grammar.is_terminal(a):
                j = transitions[(i, a)]
                add_action(action, i, a, f"s{j}", item, f"GOTO(I{i}, {a}) = I{j}")

            elif item.is_complete():
                if item.lhs == grammar.augmented_start:
                    add_action(action, i, END_MARKER, "acc", item, "S' -> S · means the whole input is S")
                else:
                    for a in all_terminals:
                        add_action(action, i, a, f"r{item.prod_index}", item,
                                   "LR(0) reduces on every terminal")

        for A in grammar.non_terminals[1:]:
            if (i, A) in transitions:
                goto_table[(i, A)] = transitions[(i, A)]

    return action, goto_table


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


def build_lr1_table(grammar, states, transitions):
    """
    Canonical LR(1) table, Dragon Book Algorithm 4.56. Also used for LALR(1)
    (Algorithm 4.59, step 3), because LALR states are sets of LR(1) items too.

    The only difference from SLR is rule (b): we reduce on the item's own
    LOOKAHEAD, not on every terminal in FOLLOW(A).
      (a) [A -> alpha · a beta, b] in I_i, GOTO(I_i, a) = I_j  ->  ACTION[i, a] = shift j
      (b) [A -> alpha ·, a] in I_i, A != S'                     ->  ACTION[i, a] = reduce A -> alpha
      (c) [S' -> S ·, $] in I_i                                  ->  ACTION[i, $] = accept
    """
    action = {}
    goto_table = {}

    for i in range(len(states)):
        for item in states[i]:
            a = item.next_symbol()

            if a is not None and grammar.is_terminal(a):
                j = transitions[(i, a)]
                add_action(action, i, a, f"s{j}", item, f"GOTO(I{i}, {a}) = I{j}")

            elif item.is_complete():
                if item.lhs == grammar.augmented_start:
                    add_action(action, i, END_MARKER, "acc", item, "S' -> S · with lookahead $")
                else:
                    b = item.lookahead
                    add_action(action, i, b, f"r{item.prod_index}", item,
                               f"the item's lookahead is '{b}'")

        for A in grammar.non_terminals[1:]:
            if (i, A) in transitions:
                goto_table[(i, A)] = transitions[(i, A)]

    return action, goto_table


class ParsingTable:
    """Everything about one parsing table, so callers don't care which method built it."""

    def __init__(self, method, states, transitions, action, goto_table, resolved=None):
        self.method = method              # "lr0", "slr", "lalr" or "clr"
        self.name = METHOD_NAMES[method]  # "SLR(1)", ...
        self.states = states
        self.transitions = transitions
        self.action = action
        self.goto_table = goto_table
        self.conflicts = find_conflicts(action)   # conflicts LEFT after precedence
        if resolved is None:
            resolved = []
        self.resolved = resolved          # conflicts settled by %left/%right/%nonassoc
        self.merged_from = None           # LALR only: LR(1) states merged into each state
        self.clr = None                   # LALR only: the CLR table it was made from

    def conflict_states(self):
        result = set()
        for c in self.conflicts:
            result.add(c["state"])
        return result


def build_parsing_table(grammar, method):
    """
    Build the LR(0), SLR(1), LALR(1) or CLR(1) table for a grammar.
      lr0  : LR(0) collection, reduce on every terminal
      slr  : LR(0) collection + FOLLOW sets         (Algorithm 4.46)
      clr  : LR(1) collection + lookaheads          (Algorithm 4.56)
      lalr : LR(1) collection, merge same cores,
             then the same construction as clr      (Algorithm 4.59)
    If the grammar has %left/%right/%nonassoc declarations, they are then
    used to resolve shift-reduce conflicts (apply_precedence).
    """
    merged_from = None
    clr = None

    if method == "lr0" or method == "slr":
        states, transitions = canonical_collection(grammar)
        if method == "lr0":
            action, goto_table = build_lr0_table(grammar, states, transitions)
        else:
            action, goto_table = build_slr_table(grammar, states, transitions)
    elif method == "clr":
        states, transitions = canonical_lr1_collection(grammar)
        action, goto_table = build_lr1_table(grammar, states, transitions)
    elif method == "lalr":
        clr = build_parsing_table(grammar, "clr")
        states, transitions, merged_from = merge_lalr_states(clr.states, clr.transitions)
        action, goto_table = build_lr1_table(grammar, states, transitions)
    else:
        raise ValueError(f"Unknown method '{method}'. Use one of: {', '.join(METHOD_NAMES)}")

    resolved = apply_precedence(grammar, action)
    table = ParsingTable(method, states, transitions, action, goto_table, resolved)
    if method == "lalr":
        table.merged_from = merged_from
        table.clr = clr
        mark_conflicts_created_by_merging(table)
    return table


def apply_precedence(grammar, action):
    """
    Resolve shift-reduce conflicts with precedence and associativity, the way
    Yacc does (Dragon Book 4.8.1 and 4.9.2). For a cell with "shift on a"
    and "reduce by production p":
      - if a has higher precedence than p  -> shift   (e.g. * after E + E)
      - if p has higher precedence than a  -> reduce  (e.g. + after E * E)
      - equal precedence: %left -> reduce, %right -> shift,
                          %nonassoc -> neither: the cell becomes an error
    p's precedence is that of its rightmost terminal (Grammar.production_precedence).
    Cells where the terminal or the production has no precedence, and all
    reduce-reduce conflicts, are left alone and stay conflicts.

    Changes 'action' in place. Returns a list of what was resolved, for printing.
    """
    resolved = []
    if not grammar.precedence:
        return resolved

    for key in sorted(action.keys(), key=lambda k: (k[0], str(k[1]))):
        cell = action[key]
        if len(cell) != 2:
            continue
        shift = None
        reduce = None
        for act in cell:
            if act.startswith("s"):
                shift = act
            elif act.startswith("r"):
                reduce = act
        if shift is None or reduce is None:
            continue

        state, a = key
        prod_index = int(reduce[1:])
        token_prec = grammar.precedence.get(a)
        prod_prec = grammar.production_precedence(prod_index)
        if token_prec is None or prod_prec is None:
            continue

        token_level, token_assoc = token_prec
        prod_level = prod_prec[0]
        prod_text = grammar.production_to_string(prod_index)

        if token_level > prod_level:
            chosen = shift
            reason = f"'{a}' has higher precedence than {prod_text}"
        elif token_level < prod_level:
            chosen = reduce
            reason = f"{prod_text} has higher precedence than '{a}'"
        elif token_assoc == "left":
            chosen = reduce
            reason = f"same precedence, '{a}' is left-associative"
        elif token_assoc == "right":
            chosen = shift
            reason = f"same precedence, '{a}' is right-associative"
        else:
            chosen = "error"
            reason = f"same precedence, '{a}' is non-associative"

        resolved.append({"state": state, "symbol": a,
                         "choices": f"{shift}/{reduce}", "chosen": chosen, "reason": reason})
        if chosen == "error":
            del action[key]                 # empty cell = syntax error
        else:
            action[key] = {chosen: cell[chosen]}

    return resolved


def print_resolutions(table):
    if not table.resolved:
        return
    print(f"{len(table.resolved)} shift-reduce conflict(s) resolved by precedence/associativity:")
    for r in table.resolved:
        print(f"  state {r['state']}, input '{r['symbol']}': {r['choices']} -> "
              f"{r['chosen']}   ({r['reason']})")


def mark_conflicts_created_by_merging(lalr_table):
    """
    A conflict in LALR state k on symbol a was CREATED by merging if none of
    the LR(1) states merged into k had a conflict on a in the CLR table.
    For such conflicts we store a note saying which LR(1) state each
    conflicting item came from. (Merging can only create reduce-reduce
    conflicts, never shift-reduce ones - see the viva notes.)
    """
    clr = lalr_table.clr
    for c in lalr_table.conflicts:
        originals = lalr_table.merged_from[c["state"]]

        conflict_already_in_clr = False
        for i in originals:
            cell = clr.action.get((i, c["symbol"]))
            if cell is not None and len(cell) > 1:
                conflict_already_in_clr = True

        if conflict_already_in_clr:
            continue

        lines = [f"Created by merging LR(1) states "
                 f"{', '.join('I' + str(i) for i in originals)} (same core). "
                 f"In the CLR table each of them was conflict-free on '{c['symbol']}':"]
        for i in originals:
            cell = clr.action.get((i, c["symbol"]))
            if cell is None:
                continue
            for act, causes in cell.items():
                for item, reason in causes:
                    lines.append(f"  LR(1) state I{i}: {act} because of item {item}")
        c["note"] = lines


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
                print(f"           because of item  {item_text(item)}   ({reason})")
        if "note" in c:
            for line in c["note"]:
                print("    " + line)


def item_text(item):
    """LR(1) items already print with brackets: [A -> a ·, b]. LR(0) items need them added."""
    text = str(item)
    if text.startswith("["):
        return text
    return "[" + text + "]"


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


def pop_option(args, name, default=None):
    """
    Remove "--name value" from the argument list and return value
    (or default if the option is not there). Used by tables.py, parser.py
    and visualize.py for --method and --out.
    """
    if name not in args:
        return default
    k = args.index(name)
    if k + 1 >= len(args):
        print(f"Missing value after {name}")
        sys.exit(1)
    value = args[k + 1]
    del args[k:k + 2]
    return value


def print_states(grammar, table):
    """Print the item sets that the table was built from."""
    if table.method == "lr0" or table.method == "slr":
        print_collection(grammar, table.states, table.transitions)
    elif table.method == "clr":
        print_lr1_collection(grammar, table.states, table.transitions,
                             "Canonical collection of LR(1) items")
    else:
        print_merge_report(grammar, table.merged_from, table.clr.states)
        print()
        print_lr1_collection(grammar, table.states, table.transitions,
                             "LALR(1) states (merged LR(1) item sets)", table.merged_from)


# ----------------------------------------------------------------------
# Comparison report: all four methods for one grammar
# ----------------------------------------------------------------------

def compare_methods(grammar):
    """
    Build all four tables and return one row (a dict) per method with the
    number of states, the remaining conflicts by kind, how many conflicts
    precedence resolved, and the verdict "is the grammar in this class?".
    """
    rows = []
    for method in METHOD_NAMES:
        table = build_parsing_table(grammar, method)
        shift_reduce = 0
        reduce_reduce = 0
        for c in table.conflicts:
            if "shift-reduce" in c["kind"]:
                shift_reduce += 1
            if "reduce-reduce" in c["kind"]:
                reduce_reduce += 1

        if table.conflicts:
            verdict = "no"
        elif table.resolved:
            # The table is usable, but only because of %left/%right: the
            # grammar itself is not in this class (it is ambiguous).
            verdict = "no (usable with precedence)"
        else:
            verdict = "yes"

        rows.append({"method": method, "name": table.name, "states": len(table.states),
                     "conflicts": len(table.conflicts), "shift_reduce": shift_reduce,
                     "reduce_reduce": reduce_reduce, "resolved": len(table.resolved),
                     "verdict": verdict})
    return rows


def print_comparison(grammar_file, rows):
    """One grammar: a row per method."""
    print(f"Comparison of LR methods for {grammar_file}")
    header = f"{'Method':<9}{'States':>7}{'Conflicts':>11}{'S/R':>6}{'R/R':>6}" \
             f"{'Resolved by prec.':>19}   In this class?"
    print(header)
    print("-" * (len(header) + 16))
    for r in rows:
        print(f"{r['name']:<9}{r['states']:>7}{r['conflicts']:>11}{r['shift_reduce']:>6}"
              f"{r['reduce_reduce']:>6}{r['resolved']:>19}   {r['verdict']}")

    strongest_needed = None
    for r in rows:
        if r["verdict"] == "yes":
            strongest_needed = r["name"]
            break
    if strongest_needed:
        print(f"=> The grammar is {strongest_needed} (and so also in every stronger class).")
    else:
        print("=> The grammar is not LR(1): it is not in any of these classes "
              "(it may be ambiguous).")


def print_comparison_summary(results):
    """
    Several grammars at once: results is a list of (grammar_file, rows).
    Each cell is "yes", "no (k)" with k conflicts, or "prec" when precedence
    removes all conflicts.
    """
    names = list(METHOD_NAMES.values())
    width = 4
    for grammar_file, rows in results:
        width = max(width, len(grammar_file))
    print(f"{'Grammar':<{width}}  " + "".join(f"{n:>10}" for n in names))
    print("-" * (width + 2 + 10 * len(names)))
    for grammar_file, rows in results:
        cells = ""
        for r in rows:
            if r["verdict"] == "yes":
                text = "yes"
            elif r["conflicts"] == 0:
                text = "prec"
            else:
                text = f"no ({r['conflicts']})"
            cells += f"{text:>10}"
        print(f"{grammar_file:<{width}}  {cells}")
    print("yes = no conflicts;  no (k) = k conflicting cells;  "
          "prec = conflicts removed by %left/%right")


if __name__ == "__main__":
    # Usage: python tables.py <grammar-file> [more files...] [--method lr0|slr|lalr|clr]
    #        python tables.py <grammar-file> [more files...] --compare
    use_utf8_output()
    args = sys.argv[1:]
    compare = "--compare" in args
    if compare:
        args.remove("--compare")
    method = pop_option(args, "--method", "slr")
    if not args or method not in METHOD_NAMES:
        print("Usage: python tables.py <grammar-file> [more files...] "
              "[--method lr0|slr|lalr|clr] [--compare]")
        sys.exit(1)

    if compare:
        results = []
        for filename in args:
            rows = compare_methods(load_grammar(filename))
            results.append((filename, rows))
            print_comparison(filename, rows)
            print()
        if len(results) > 1:
            print_comparison_summary(results)
        sys.exit(0)

    for filename in args:
        print("=" * 70)
        print("Grammar file:", filename)
        print("=" * 70)
        g = load_grammar(filename)
        print_grammar_info(g)
        print()

        table = build_parsing_table(g, method)
        print_states(g, table)
        print()

        print(f"{table.name} parsing table:")
        print_table(g, len(table.states), table.action, table.goto_table)
        print()
        print_resolutions(table)
        explain_conflicts(g, table.conflicts, table.name)
        print()
