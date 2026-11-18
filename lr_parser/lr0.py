"""
lr0.py - Phase 2: LR(0) items, CLOSURE, GOTO and the canonical LR(0) collection.

Based on labs/4.6-slr_parser.py, following Dragon Book Section 4.6.2:
  - LR(0) item          : a production with a dot in its body, e.g. E -> E · + T
  - CLOSURE(I)          : Figure 4.32
  - GOTO(I, X)          : Section 4.6.2 "The Function GOTO"
  - items(G')           : Figure 4.33, the canonical LR(0) collection

The epsilon bug fix:
  Every item remembers the NUMBER of the production it came from
  (prod_index). When we reduce, we use that number directly instead of
  searching for the rule with rules.index(), which used to fail because
  items stored [] but rules stored ["epsilon"].
  An epsilon production A -> epsilon has an empty body, so its only
  item is  A -> ·  and it is complete (a reduce item) right away.
"""

import sys
from grammar import load_grammar, use_utf8_output

DOT = "·"


class LR0Item:
    """One LR(0) item: production number + lhs + rhs + position of the dot."""

    def __init__(self, prod_index, lhs, rhs, dot):
        self.prod_index = prod_index   # which production (0 = S' -> S)
        self.lhs = lhs
        self.rhs = rhs                 # list of symbols; [] for epsilon
        self.dot = dot                 # dot is BEFORE rhs[dot]

    def next_symbol(self):
        """The symbol right after the dot, or None if the dot is at the end."""
        if self.dot < len(self.rhs):
            return self.rhs[self.dot]
        return None

    def advance(self):
        """Move the dot one symbol to the right:  A -> a · X b  becomes  A -> a X · b"""
        return LR0Item(self.prod_index, self.lhs, self.rhs, self.dot + 1)

    def is_complete(self):
        """True for A -> alpha ·  (a reduce item). For A -> epsilon this is A -> ·"""
        return self.dot == len(self.rhs)

    def is_kernel(self, grammar):
        """
        Kernel items (Dragon Book): the start item S' -> · S, plus every item
        whose dot is not at the left end. The other items are added by CLOSURE.
        """
        return self.dot > 0 or self.lhs == grammar.augmented_start

    # Two items are the same if they have the same production and dot.
    def __eq__(self, other):
        return (self.prod_index, self.dot) == (other.prod_index, other.dot)

    def __hash__(self):
        return hash((self.prod_index, self.dot))

    def __repr__(self):
        parts = self.rhs[:self.dot] + [DOT] + self.rhs[self.dot:]
        return self.lhs + " -> " + " ".join(parts)


def closure(items, grammar):
    """
    CLOSURE(I), Dragon Book Figure 4.32:
      Start with J = I.
      For every item A -> alpha · B beta in J, and every production B -> gamma,
      add B -> · gamma to J if it is not already there.
      Repeat until nothing new is added.

    We return a LIST (kernel items first, then items in the order they were
    added) so the printout is easy to read. The work-list index i walks over
    J while it grows, so every item - including newly added ones - is
    examined exactly once.
    """
    result = list(items)
    i = 0
    while i < len(result):
        B = result[i].next_symbol()
        if B is not None and grammar.is_non_terminal(B):
            for prod_index in range(len(grammar.productions)):
                lhs, rhs = grammar.productions[prod_index]
                if lhs == B:
                    new_item = LR0Item(prod_index, lhs, rhs, 0)
                    if new_item not in result:
                        result.append(new_item)
        i += 1
    return result


def goto(items, X, grammar):
    """
    GOTO(I, X): take every item  A -> alpha · X beta  in I, move the dot over X
    to get  A -> alpha X · beta,  then take the CLOSURE of that set.
    Returns an empty list if no item in I has X after the dot.
    """
    moved = []
    for item in items:
        if item.next_symbol() == X:
            moved.append(item.advance())
    if not moved:
        return []
    return closure(moved, grammar)


def canonical_collection(grammar):
    """
    items(G'), Dragon Book Figure 4.33:
      C = { CLOSURE({ S' -> · S }) }
      repeat
        for each set of items I in C
          for each grammar symbol X
            if GOTO(I, X) is not empty and not in C, add it to C
      until no new sets are added.

    We process states in order (a work-list), and for each state try the
    non-terminals first and then the terminals. This numbers the states
    I0, I1, ... exactly as in Dragon Book Figure 4.31.

    Returns:
      states      : list of item lists; states[i] is the set I_i
      transitions : dict (i, X) -> j   meaning GOTO(I_i, X) = I_j
    """
    start_item = LR0Item(0, grammar.augmented_start, grammar.productions[0][1], 0)
    states = [closure([start_item], grammar)]

    # To check "is this set already in C?" we compare frozensets, because
    # the order of items inside a set does not matter.
    index_of = {frozenset(states[0]): 0}
    transitions = {}

    # S' never appears after a dot, so we skip it.
    symbols = grammar.non_terminals[1:] + grammar.terminals

    i = 0
    while i < len(states):          # states grows while we loop
        for X in symbols:
            target = goto(states[i], X, grammar)
            if not target:
                continue
            key = frozenset(target)
            if key not in index_of:
                index_of[key] = len(states)
                states.append(target)
            transitions[(i, X)] = index_of[key]
        i += 1

    return states, transitions


def print_collection(grammar, states, transitions):
    """Print every item set, marking kernel and closure items, plus its GOTOs."""
    print(f"Canonical collection of LR(0) items: {len(states)} states")
    for i in range(len(states)):
        print()
        print(f"I{i}:")
        for item in states[i]:
            if item.is_kernel(grammar):
                tag = ""
            else:
                tag = "(closure)"
            print(f"    {str(item):<28}{tag}")

        moves = []
        for X in grammar.non_terminals[1:] + grammar.terminals:
            if (i, X) in transitions:
                moves.append(f"GOTO(I{i}, {X}) = I{transitions[(i, X)]}")
        if moves:
            print("    " + "   ".join(moves))


if __name__ == "__main__":
    # Usage: python lr0.py ../grammars/expr.txt
    use_utf8_output()
    if len(sys.argv) < 2:
        print("Usage: python lr0.py <grammar-file>")
        sys.exit(1)
    g = load_grammar(sys.argv[1])
    C, trans = canonical_collection(g)
    print_collection(g, C, trans)
