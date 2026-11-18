"""
lexer.py - Phase 4: turns source text like  "count + 10 * (x + y)"  into tokens
                    id + num * ( id + id )   for the LR parser.

Based on my transition-diagram lexer in labs/3.4-transition_diagram.py
(Dragon Book Section 3.4: recognizing tokens with transition diagrams).

How a token's KIND is chosen, so that it matches the grammar's terminals:
  - identifier  (letter (letter|digit)*)  -> "id"
  - number      (digits, optional .digits, optional E[+-]digits) -> "num"
  - operator / punctuation                -> the lexeme itself, e.g. "+", "<=", "("
  - reserved words: if an identifier's lexeme is itself a terminal of the
    grammar (e.g. "if", or "a" in reduce_reduce.txt), its kind is that word.
    This is the Dragon Book trick of recognizing keywords with the identifier
    diagram and then checking a table of reserved words (Section 3.4.3).

Every token keeps its LEXEME (the actual text) and its LINE and COLUMN,
so the parse tree can show "id (count)" and errors can say where they are.
"""

import sys


class Token:
    """One token: kind (the grammar terminal), lexeme (the text), and position."""

    def __init__(self, kind, lexeme, line, column):
        self.kind = kind
        self.lexeme = lexeme
        self.line = line
        self.column = column

    def __repr__(self):
        if self.lexeme == self.kind:
            return self.kind
        return f"{self.kind}({self.lexeme})"


class LexicalError(Exception):
    """Raised for a character sequence that no transition diagram accepts."""

    def __init__(self, message, line, column):
        super().__init__(f"Lexical error at line {line}, column {column}: {message}")
        self.line = line
        self.column = column


class TransitionDiagram:
    """
    A transition diagram (DFA), as in labs/3.4.

    edges     : list of (from_state, label, to_state). A label is "letter",
                "digit", "other" (any character not on another edge) or a
                literal character.
    accepting : dict  state -> (category, retract).  retract=True means the
                last character read is NOT part of the lexeme (the "*" states
                in the Dragon Book diagrams), so we move the pointer back.
    State 0 is the start state.
    """

    def __init__(self, name, edges, accepting):
        self.name = name
        self.edges = edges
        self.accepting = accepting

    @staticmethod
    def matches(label, c):
        if c is None:                  # end of input matches nothing but "other"
            return False
        if label == "letter":
            return c.isalpha() or c == "_"
        if label == "digit":
            return c.isdigit()
        return label == c

    def step(self, state, c):
        """Follow one edge from 'state' on character c. None means no edge (fail)."""
        other_target = None
        for from_state, label, to_state in self.edges:
            if from_state != state:
                continue
            if label == "other":
                other_target = to_state
            elif self.matches(label, c):
                return to_state
        return other_target

    def run(self, text, start):
        """
        Simulate the diagram from text[start].
        Returns (category, lexeme, next_position), or None if the diagram fails.
        """
        state = 0
        pos = start
        while True:
            if pos < len(text):
                c = text[pos]
            else:
                c = None                       # end of input
            next_state = self.step(state, c)
            if next_state is None:
                return None
            state = next_state
            if c is not None:
                pos += 1
            if state in self.accepting:
                category, retract = self.accepting[state]
                if retract and c is not None:
                    pos -= 1                   # retract the forward pointer
                return category, text[start:pos], pos


def build_diagrams():
    """The three diagrams from labs/3.4: identifiers, numbers, relational operators."""
    identifier = TransitionDiagram("identifier", [
        (0, "letter", 1),
        (1, "letter", 1), (1, "digit", 1),
        (1, "other", 2),
    ], {2: ("id", True)})

    # Integer, decimal and scientific numbers all become the terminal "num".
    number = TransitionDiagram("number", [
        (0, "digit", 1), (1, "digit", 1),
        (1, ".", 2), (2, "digit", 3), (3, "digit", 3),
        (1, "E", 4), (3, "E", 4),
        (4, "+", 5), (4, "-", 5), (4, "digit", 6), (5, "digit", 6),
        (6, "digit", 6),
        (1, "other", 7), (3, "other", 8), (6, "other", 9),
    ], {7: ("num", True), 8: ("num", True), 9: ("num", True)})

    # Relational, assignment and logical operators. Category "op" means
    # "the token kind is the lexeme itself", e.g. "<=" or "=".
    operator = TransitionDiagram("operator", [
        (0, "<", 1), (1, "=", 2), (1, "other", 3),
        (0, ">", 4), (4, "=", 5), (4, "other", 6),
        (0, "=", 7), (7, "=", 8), (7, "other", 9),
        (0, "!", 10), (10, "=", 11), (10, "other", 12),
        (0, "&", 13), (13, "&", 14),
        (0, "|", 15), (15, "|", 16),
    ], {2: ("op", False), 3: ("op", True),      # <=  <
        5: ("op", False), 6: ("op", True),      # >=  >
        8: ("op", False), 9: ("op", True),      # ==  =
        11: ("op", False), 12: ("op", True),    # !=  !
        14: ("op", False), 16: ("op", False)})  # &&  ||

    return [identifier, number, operator]


# Single characters that are always a token on their own (kind = the character)
SINGLE_CHARS = "()[]{};,+-*/%"


def line_and_column(text, pos):
    """1-based line and column of text[pos]."""
    line = text.count("\n", 0, pos) + 1
    last_newline = text.rfind("\n", 0, pos)   # -1 if we are on the first line
    column = pos - last_newline
    return line, column


def tokenize(text, keywords=None):
    """
    Split 'text' into a list of Token objects.
    keywords: words that are reserved (normally: the grammar's terminals).
    Raises LexicalError on a character that starts no valid token.
    """
    if keywords is None:
        keywords = set()
    diagrams = build_diagrams()
    tokens = []
    pos = 0

    while pos < len(text):
        c = text[pos]

        # Skip white space
        if c.isspace():
            pos += 1
            continue

        # Skip comments:  // to end of line,  /* ... */
        if text.startswith("//", pos):
            newline = text.find("\n", pos)
            if newline == -1:
                pos = len(text)
            else:
                pos = newline
            continue
        if text.startswith("/*", pos):
            end = text.find("*/", pos + 2)
            if end == -1:
                line, column = line_and_column(text, pos)
                raise LexicalError("comment is never closed with */", line, column)
            pos = end + 2
            continue

        line, column = line_and_column(text, pos)

        # Try each transition diagram in turn (as in labs/3.4)
        match = None
        for diagram in diagrams:
            match = diagram.run(text, pos)
            if match is not None:
                break

        if match is not None:
            category, lexeme, new_pos = match
            if category == "id" and lexeme in keywords:
                kind = lexeme              # reserved word of this grammar
            elif category == "op":
                kind = lexeme              # operator: kind is the symbol itself
            else:
                kind = category            # "id" or "num"
            tokens.append(Token(kind, lexeme, line, column))
            pos = new_pos
        elif c in SINGLE_CHARS:
            tokens.append(Token(c, c, line, column))
            pos += 1
        else:
            if c.isdigit():
                message = "malformed number"
            else:
                message = f"unexpected character '{c}'"
            raise LexicalError(message, line, column)

    return tokens


def print_tokens(tokens):
    print(f"{'LEXEME':<12}{'TOKEN':<8}{'LINE:COL'}")
    for t in tokens:
        print(f"{t.lexeme:<12}{t.kind:<8}{t.line}:{t.column}")


if __name__ == "__main__":
    # Usage: python lexer.py "count + 10 * (x + y)"
    sys.stdout.reconfigure(encoding="utf-8")
    source = sys.argv[1] if len(sys.argv) > 1 else "count + 10 * (x + y)"
    try:
        print_tokens(tokenize(source))
    except LexicalError as e:
        print(e)
