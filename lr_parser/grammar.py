"""
grammar.py - Phase 1 of the LR Parser Generator.

What this file does:
  1. Reads a grammar file (one rule per line, e.g.  E -> E + T | T).
  2. Finds the non-terminals (symbols on a left-hand side) and the
     terminals (every other symbol used on a right-hand side).
  3. Augments the grammar with a new start production  S' -> S
     (Dragon Book, Section 4.6.2 "Augmented grammar").
  4. Computes FIRST and FOLLOW sets (Dragon Book, Section 4.4.2).

How epsilon is stored:
  - In the grammar file the word "epsilon" means the empty string.
  - Inside the program an epsilon production is an EMPTY LIST:
        A -> epsilon     is stored as   ("A", [])
    So every right-hand side is always a list of symbols, and an
    empty rule simply has length 0. (This avoids the old bug in
    labs/4.6 where items used [] but rules used ["epsilon"].)
  - Inside FIRST sets we still need a marker meaning "can derive the
    empty string". For that we use the constant EPSILON below.

FIRST/FOLLOW code is adapted from labs/4.4-top_down_ll1_parser.py.
"""

import io
import sys

EPSILON = "ε"        # marker used inside FIRST sets for the empty string
END_MARKER = "$"     # end-of-input marker used in FOLLOW sets

# Words the user may write in a grammar file to mean "empty string".
EPSILON_WORDS = ["epsilon", "ε"]


def use_utf8_output():
    """
    Make print() use UTF-8 so ε and · show correctly on the Windows console.
    The isinstance check is needed because sys.stdout is not always a real
    text stream (e.g. when the tests capture output), and only real text
    streams have reconfigure().
    """
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")


class Grammar:
    """
    Holds an augmented grammar.

    Attributes:
      start_symbol      original start symbol S (LHS of the first rule)
      augmented_start   the new start symbol S'
      productions       numbered list of (lhs, rhs_list) pairs.
                        productions[0] is always S' -> S, so the user's
                        own rules are numbered 1, 2, 3 ... exactly like
                        the Dragon Book numbers them.
      rules_for         dict: non-terminal -> list of its right-hand sides
      non_terminals     list, in order of first appearance (S' first)
      terminals         list, in order of first appearance (no "$")
      first, follow     dicts filled in by compute_first / compute_follow
      precedence        dict: terminal -> (level, associativity) from %left,
                        %right, %nonassoc lines (empty if there are none)
    """

    def __init__(self, rule_list, precedence=None):
        # rule_list: list of (lhs, rhs_list) in the order they appeared in the file.
        # precedence: from parse_precedence_lines(), or None.
        if not rule_list:
            raise ValueError("Grammar is empty: no rules were found.")

        # --- Step 1: the start symbol is the LHS of the first rule ---
        self.start_symbol = rule_list[0][0]

        # --- Step 2: non-terminals = every symbol that appears on a LHS ---
        original_non_terminals = []
        for lhs, rhs in rule_list:
            if lhs not in original_non_terminals:
                original_non_terminals.append(lhs)

        # --- Step 3: terminals = every RHS symbol that is NOT a non-terminal ---
        self.terminals = []
        for lhs, rhs in rule_list:
            for symbol in rhs:
                if symbol not in original_non_terminals and symbol not in self.terminals:
                    self.terminals.append(symbol)

        if END_MARKER in self.terminals:
            raise ValueError("'$' is reserved for end of input; do not use it in the grammar.")

        # --- Step 4: augment the grammar with S' -> S ---
        self.augmented_start = self.make_augmented_name(original_non_terminals)
        self.non_terminals = [self.augmented_start] + original_non_terminals

        self.productions = [(self.augmented_start, [self.start_symbol])]
        for lhs, rhs in rule_list:
            self.productions.append((lhs, rhs))

        # rules_for["E"] = [["E", "+", "T"], ["T"]]  (handy for closure later)
        self.rules_for = {}
        for nt in self.non_terminals:
            self.rules_for[nt] = []
        for lhs, rhs in self.productions:
            self.rules_for[lhs].append(rhs)

        # --- Step 5: FIRST and FOLLOW ---
        self.first = compute_first(self)
        self.follow = compute_follow(self)

        # --- Step 6: precedence declarations (only terminals can have one) ---
        if precedence is None:
            precedence = {}
        for symbol in precedence:
            if symbol not in self.terminals:
                raise ValueError(f"Precedence declared for '{symbol}', "
                                 f"which is not a terminal of this grammar.")
        self.precedence = precedence

    def production_precedence(self, index):
        """
        Dragon Book 4.8.1 / Yacc: a production has the precedence and
        associativity of its RIGHTMOST terminal. E -> E + E gets the
        precedence of '+'. Returns (level, associativity) or None.
        """
        lhs, rhs = self.productions[index]
        for symbol in reversed(rhs):
            if symbol in self.terminals:
                return self.precedence.get(symbol)
        return None

    def make_augmented_name(self, used_names):
        """
        Return S' for start symbol S. If that name is already used in the
        grammar (e.g. the grammar already has E'), keep adding primes: E''.
        """
        name = self.start_symbol + "'"
        while name in used_names:
            name = name + "'"
        return name

    def is_terminal(self, symbol):
        return symbol in self.terminals or symbol == END_MARKER

    def is_non_terminal(self, symbol):
        return symbol in self.non_terminals

    def production_to_string(self, index):
        lhs, rhs = self.productions[index]
        return lhs + " -> " + rhs_to_string(rhs)


# ----------------------------------------------------------------------
# Reading the grammar file
# ----------------------------------------------------------------------

def parse_grammar_lines(lines):
    """
    Turn lines like  "E -> E + T | T"  into a list of (lhs, rhs_list).
    Based on parse_grammar_input() from labs/4.2, with error messages added.
    """
    rule_list = []
    line_number = 0
    for line in lines:
        line_number += 1
        line = line.strip()

        # Skip blank lines, comments, and precedence lines
        # (%left etc. are read by parse_precedence_lines)
        if line == "" or line.startswith("#") or line.startswith("%"):
            continue

        if "->" not in line:
            raise ValueError(f"Line {line_number}: missing '->' in: {line}")

        lhs, rhs_all = line.split("->", 1)
        lhs = lhs.strip()
        if lhs == "" or len(lhs.split()) != 1:
            raise ValueError(f"Line {line_number}: left-hand side must be exactly one symbol: {line}")

        # Each alternative separated by | becomes its own production
        for alternative in rhs_all.split("|"):
            symbols = alternative.split()

            # Remove the word "epsilon": "A -> epsilon" becomes A -> []
            rhs = []
            for symbol in symbols:
                if symbol not in EPSILON_WORDS:
                    rhs.append(symbol)

            if len(symbols) == 0:
                raise ValueError(f"Line {line_number}: empty alternative; write 'epsilon' for an empty rule.")

            rule_list.append((lhs, rhs))
    return rule_list


ASSOCIATIVITY_WORDS = {"%left": "left", "%right": "right", "%nonassoc": "nonassoc"}


def parse_precedence_lines(lines):
    """
    Read Yacc-style declarations (Dragon Book 4.8.1 and 4.9.2):
        %left + -
        %left * /
        %right ^
    All tokens on one line have the same precedence; LATER lines have
    HIGHER precedence. Returns a dict  terminal -> (level, associativity),
    e.g. {"+": (1, "left"), "*": (2, "left")}.
    """
    precedence = {}
    level = 0
    line_number = 0
    for line in lines:
        line_number += 1
        words = line.split()
        if not words or not words[0].startswith("%"):
            continue
        if words[0] not in ASSOCIATIVITY_WORDS:
            raise ValueError(f"Line {line_number}: unknown declaration '{words[0]}' "
                             f"(use %left, %right or %nonassoc)")
        if len(words) < 2:
            raise ValueError(f"Line {line_number}: '{words[0]}' needs at least one token")

        level += 1
        for token in words[1:]:
            if token in precedence:
                raise ValueError(f"Line {line_number}: precedence of '{token}' declared twice")
            precedence[token] = (level, ASSOCIATIVITY_WORDS[words[0]])
    return precedence


def load_grammar(filename):
    """Read a grammar file and return a fully built Grammar object."""
    with open(filename, encoding="utf-8") as f:
        lines = f.readlines()
    rule_list = parse_grammar_lines(lines)
    precedence = parse_precedence_lines(lines)
    return Grammar(rule_list, precedence)


# ----------------------------------------------------------------------
# FIRST and FOLLOW  (adapted from labs/4.4-top_down_ll1_parser.py)
# ----------------------------------------------------------------------

def compute_first(grammar):
    """
    Dragon Book 4.4.2, rules for FIRST(X):
      1. If X is a terminal, FIRST(X) = {X}.
      2. If X -> epsilon is a production, add epsilon to FIRST(X).
      3. If X -> Y1 Y2 ... Yk, add FIRST(Y1) - {epsilon}. If Y1 can derive
         epsilon, also add FIRST(Y2) - {epsilon}, and so on. If ALL of
         Y1..Yk can derive epsilon, add epsilon to FIRST(X).
    We repeat until no set changes (a "fixed point").
    """
    first = {}

    # Rule 1: terminals (and $) have themselves as FIRST
    for t in grammar.terminals:
        first[t] = {t}
    first[END_MARKER] = {END_MARKER}

    # Non-terminals start empty
    for nt in grammar.non_terminals:
        first[nt] = set()

    changed = True
    while changed:
        changed = False
        for lhs, rhs in grammar.productions:
            # FIRST of the whole right-hand side (rules 2 and 3 together:
            # an empty rhs gives {epsilon})
            rhs_first = first_of_sequence(rhs, first)

            size_before = len(first[lhs])
            first[lhs].update(rhs_first)
            if len(first[lhs]) > size_before:
                changed = True
    return first


def first_of_sequence(symbols, first):
    """
    FIRST of a string of symbols  X1 X2 ... Xn  (used by FOLLOW, and later
    by CLR(1) closure for the lookahead FIRST(beta a)).
    An empty list means the empty string, so its FIRST is {epsilon}.
    """
    result = set()
    for symbol in symbols:
        symbol_first = first[symbol]
        result.update(symbol_first - {EPSILON})
        if EPSILON not in symbol_first:
            # This symbol cannot vanish, so later symbols don't matter.
            return result
    # Every symbol could derive epsilon (or the list was empty)
    result.add(EPSILON)
    return result


def compute_follow(grammar):
    """
    Dragon Book 4.4.2, rules for FOLLOW(A):
      1. Put $ in FOLLOW(S), where S is the start symbol.
         (We use the augmented start S'; FOLLOW(S) gets $ through S' -> S.)
      2. If A -> alpha B beta, everything in FIRST(beta) except epsilon
         is in FOLLOW(B).
      3. If A -> alpha B, or A -> alpha B beta where FIRST(beta) contains
         epsilon, then everything in FOLLOW(A) is in FOLLOW(B).
    We repeat until no set changes.
    """
    first = grammar.first
    follow = {}
    for nt in grammar.non_terminals:
        follow[nt] = set()

    # Rule 1
    follow[grammar.augmented_start].add(END_MARKER)

    changed = True
    while changed:
        changed = False
        for lhs, rhs in grammar.productions:
            for i in range(len(rhs)):
                B = rhs[i]
                if not grammar.is_non_terminal(B):
                    continue

                beta = rhs[i + 1:]
                beta_first = first_of_sequence(beta, first)
                size_before = len(follow[B])

                # Rule 2
                follow[B].update(beta_first - {EPSILON})

                # Rule 3 (beta is empty or can derive epsilon)
                if EPSILON in beta_first:
                    follow[B].update(follow[lhs])

                if len(follow[B]) > size_before:
                    changed = True
    return follow


# ----------------------------------------------------------------------
# Printing helpers
# ----------------------------------------------------------------------

def rhs_to_string(rhs):
    if len(rhs) == 0:
        return EPSILON
    return " ".join(rhs)


def set_to_string(symbol_set, grammar):
    """Print a set in a fixed order: terminals as in the grammar, then $, then epsilon."""
    order = grammar.terminals + [END_MARKER, EPSILON]
    ordered = []
    for symbol in order:
        if symbol in symbol_set:
            ordered.append(symbol)
    return "{ " + ", ".join(ordered) + " }"


def precedence_to_string(grammar):
    """E.g. "%left +  <  %left *"  (lowest precedence first)."""
    levels = {}
    for token, (level, assoc) in grammar.precedence.items():
        if level not in levels:
            levels[level] = (assoc, [])
        levels[level][1].append(token)
    parts = []
    for level in sorted(levels):
        assoc, tokens = levels[level]
        parts.append(f"%{assoc} {' '.join(tokens)}")
    return "  <  ".join(parts)


def print_grammar_info(grammar):
    print("Augmented grammar (numbered productions):")
    for i in range(len(grammar.productions)):
        print(f"  ({i}) {grammar.production_to_string(i)}")
    print()
    print("Start symbol     :", grammar.start_symbol)
    print("Augmented start  :", grammar.augmented_start)
    print("Non-terminals    :", ", ".join(grammar.non_terminals))
    print("Terminals        :", ", ".join(grammar.terminals))
    if grammar.precedence:
        print("Precedence       :", precedence_to_string(grammar))
    print()

    width = max(len(nt) for nt in grammar.non_terminals)
    print("FIRST sets:")
    for nt in grammar.non_terminals:
        print(f"  FIRST({nt}){' ' * (width - len(nt))} = {set_to_string(grammar.first[nt], grammar)}")
    print()
    print("FOLLOW sets:")
    for nt in grammar.non_terminals:
        print(f"  FOLLOW({nt}){' ' * (width - len(nt))} = {set_to_string(grammar.follow[nt], grammar)}")


if __name__ == "__main__":
    # Usage: python grammar.py ../grammars/expr.txt
    # Make sure ε prints correctly on the Windows console.
    use_utf8_output()

    if len(sys.argv) < 2:
        print("Usage: python grammar.py <grammar-file>")
        sys.exit(1)

    for filename in sys.argv[1:]:
        print("=" * 60)
        print("Grammar file:", filename)
        print("=" * 60)
        g = load_grammar(filename)
        print_grammar_info(g)
        print()
