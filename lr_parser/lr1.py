"""
lr1.py - Phase 5: LR(1) items, CLOSURE, GOTO, the canonical LR(1) collection,
and the LALR(1) states made by merging LR(1) states with the same core.

Dragon Book Section 4.7:
  - LR(1) item      : [A -> alpha · beta, a]   a = the LOOKAHEAD terminal (or $).
                      The lookahead only matters when the dot is at the end:
                      [A -> alpha ·, a] means "reduce by A -> alpha only if
                      the next input symbol is a".
  - CLOSURE(I)      : Figure 4.40
  - GOTO(I, X)      : Figure 4.40
  - items(G')       : Figure 4.40, the canonical collection of sets of LR(1) items
  - LALR(1) states  : Algorithm 4.59 - merge the sets that have the same CORE
                      (the same LR(0) items, ignoring lookaheads).
"""

import sys
from grammar import load_grammar, first_of_sequence, END_MARKER, use_utf8_output
from lr0 import LR0Item


class LR1Item(LR0Item):
    """
    An LR(1) item is an LR(0) item plus one lookahead terminal.
    It inherits next_symbol(), is_complete() and is_kernel() from LR0Item.
    """

    def __init__(self, prod_index, lhs, rhs, dot, lookahead):
        super().__init__(prod_index, lhs, rhs, dot)
        self.lookahead = lookahead

    def advance(self):
        """Move the dot one place right. The lookahead does NOT change."""
        return LR1Item(self.prod_index, self.lhs, self.rhs, self.dot + 1, self.lookahead)

    def core(self):
        """The core = the LR(0) part of the item (production and dot), without the lookahead."""
        return (self.prod_index, self.dot)

    def core_string(self):
        return LR0Item.__repr__(self)       # "A -> alpha · beta"

    # Two LR(1) items are equal only if the lookahead is equal too.
    def __eq__(self, other):
        return (self.prod_index, self.dot, self.lookahead) == \
               (other.prod_index, other.dot, other.lookahead)

    def __hash__(self):
        return hash((self.prod_index, self.dot, self.lookahead))

    def __repr__(self):
        return f"[{self.core_string()}, {self.lookahead}]"


def in_terminal_order(grammar, symbols):
    """Return the given terminals as a list in grammar order, with $ last (for stable output)."""
    ordered = []
    for t in grammar.terminals + [END_MARKER]:
        if t in symbols:
            ordered.append(t)
    return ordered


def closure_lr1(items, grammar):
    """
    CLOSURE(I), Dragon Book Figure 4.40:
      repeat
        for each item [A -> alpha · B beta, a] in I
          for each production B -> gamma
            for each terminal b in FIRST(beta a)
              add [B -> · gamma, b] to I
      until no more items are added.

    Why FIRST(beta a)?  After B is reduced, the parser will see what comes
    after B in this item: first beta, and if beta can vanish, then a.
    Because a is a terminal (or $), FIRST(beta a) never contains epsilon.
    """
    result = list(items)
    i = 0
    while i < len(result):
        item = result[i]
        B = item.next_symbol()
        if B is not None and grammar.is_non_terminal(B):
            beta = item.rhs[item.dot + 1:]
            lookaheads = first_of_sequence(beta + [item.lookahead], grammar.first)
            for prod_index in range(len(grammar.productions)):
                lhs, rhs = grammar.productions[prod_index]
                if lhs != B:
                    continue
                for b in in_terminal_order(grammar, lookaheads):
                    new_item = LR1Item(prod_index, lhs, rhs, 0, b)
                    if new_item not in result:
                        result.append(new_item)
        i += 1
    return result


def goto_lr1(items, X, grammar):
    """GOTO(I, X): move the dot over X in every item that has X after the dot, then CLOSURE."""
    moved = []
    for item in items:
        if item.next_symbol() == X:
            moved.append(item.advance())
    if not moved:
        return []
    return closure_lr1(moved, grammar)


def canonical_lr1_collection(grammar):
    """
    items(G'), Dragon Book Figure 4.40. Same loop as the LR(0) collection
    (lr0.canonical_collection), but it starts from [S' -> · S, $] and uses
    the LR(1) closure and GOTO. Non-terminals are tried before terminals,
    which numbers the states exactly as in Figure 4.41.

    Returns (states, transitions) like lr0.canonical_collection.
    """
    start_item = LR1Item(0, grammar.augmented_start, grammar.productions[0][1], 0, END_MARKER)
    states = [closure_lr1([start_item], grammar)]
    index_of = {frozenset(states[0]): 0}
    transitions = {}
    symbols = grammar.non_terminals[1:] + grammar.terminals

    i = 0
    while i < len(states):
        for X in symbols:
            target = goto_lr1(states[i], X, grammar)
            if not target:
                continue
            key = frozenset(target)
            if key not in index_of:
                index_of[key] = len(states)
                states.append(target)
            transitions[(i, X)] = index_of[key]
        i += 1

    return states, transitions


# ----------------------------------------------------------------------
# LALR(1): merge states with the same core (Algorithm 4.59)
# ----------------------------------------------------------------------

def state_core(items):
    """The core of a set of LR(1) items: the set of its LR(0) items."""
    core = set()
    for item in items:
        core.add(item.core())
    return frozenset(core)


def merge_lalr_states(lr1_states, lr1_transitions):
    """
    Algorithm 4.59, steps 1-2 and the GOTO part of step 4:
      - group the LR(1) states by core; each group becomes ONE LALR state
        whose items are the union of the group's items
        (same LR(0) items, lookaheads combined);
      - if GOTO(I, X) = J in the LR(1) automaton, then in the LALR automaton
        GOTO(group of I, X) = group of J. (States with the same core have
        GOTOs with the same core, so this is well defined.)

    LALR states are numbered in order of their first LR(1) state.

    Returns:
      states      : list of merged item lists
      transitions : dict (k, X) -> m  for the merged states
      merged_from : merged_from[k] = list of LR(1) state numbers merged into state k
    """
    new_number = {}        # core -> LALR state number
    lalr_number_of = []    # lalr_number_of[i] = LALR state that LR(1) state i went into
    states = []
    merged_from = []

    for i in range(len(lr1_states)):
        core = state_core(lr1_states[i])
        if core not in new_number:
            new_number[core] = len(states)
            states.append(list(lr1_states[i]))
            merged_from.append([i])
        else:
            k = new_number[core]
            merged_from[k].append(i)
            for item in lr1_states[i]:          # union of the item sets
                if item not in states[k]:
                    states[k].append(item)
        lalr_number_of.append(new_number[core])

    transitions = {}
    for (i, X), j in lr1_transitions.items():
        transitions[(lalr_number_of[i], X)] = lalr_number_of[j]

    return states, transitions, merged_from


# ----------------------------------------------------------------------
# Printing
# ----------------------------------------------------------------------

def group_by_core(grammar, items):
    """
    For printing, items with the same core are shown on one line with all
    their lookaheads, as the book does:  [C -> c · C, c/d]
    Returns a list of (first_item, lookahead_list) in order of appearance.
    """
    groups = []
    position = {}
    for item in items:
        key = item.core()
        if key not in position:
            position[key] = len(groups)
            groups.append((item, set()))
        groups[position[key]][1].add(item.lookahead)

    result = []
    for item, lookaheads in groups:
        result.append((item, in_terminal_order(grammar, lookaheads)))
    return result


def item_group_text(item, lookaheads):
    return f"{item.core_string()}, {'/'.join(lookaheads)}"


def print_lr1_collection(grammar, states, transitions, title, merged_from=None):
    print(f"{title}: {len(states)} states")
    for i in range(len(states)):
        print()
        header = f"I{i}:"
        if merged_from is not None and len(merged_from[i]) > 1:
            numbers = " + ".join(f"I{j}" for j in merged_from[i])
            header = f"I{i}:   (merged from LR(1) states {numbers})"
        print(header)
        for item, lookaheads in group_by_core(grammar, states[i]):
            if item.is_kernel(grammar):
                tag = ""
            else:
                tag = "(closure)"
            print(f"    {'[' + item_group_text(item, lookaheads) + ']':<34}{tag}")

        moves = []
        for X in grammar.non_terminals[1:] + grammar.terminals:
            if (i, X) in transitions:
                moves.append(f"GOTO(I{i}, {X}) = I{transitions[(i, X)]}")
        if moves:
            print("    " + "   ".join(moves))


def print_merge_report(grammar, merged_from, lr1_states):
    """Which LR(1) states were merged into each LALR state, and on which core."""
    print(f"LALR(1) merging: {len(lr1_states)} LR(1) states -> {len(merged_from)} LALR(1) states")
    merged_any = False
    for k in range(len(merged_from)):
        group = merged_from[k]
        if len(group) < 2:
            continue
        merged_any = True
        numbers = ", ".join(f"I{j}" for j in group)
        kernel = []
        for item, lookaheads in group_by_core(grammar, lr1_states[group[0]]):
            if item.is_kernel(grammar):
                kernel.append(item.core_string())
        print(f"  LALR state {k} = LR(1) states {numbers}   (common core: {'; '.join(kernel)})")
    if not merged_any:
        print("  No two LR(1) states have the same core, so nothing was merged.")


if __name__ == "__main__":
    # Usage: python lr1.py <grammar-file>
    use_utf8_output()
    if len(sys.argv) < 2:
        print("Usage: python lr1.py <grammar-file>")
        sys.exit(1)
    g = load_grammar(sys.argv[1])
    C, trans = canonical_lr1_collection(g)
    print_lr1_collection(g, C, trans, "Canonical collection of LR(1) items")
