# Project: LR Parser Generator & Visualizer (SLR(1), CLR(1), LALR(1))

## Context
This is my university Compiler Design lab project (7th semester, 15 marks).
The teacher grades on DEPTH of one concept. The concept is bottom-up LR parsing.
I must be able to explain every line of code at the viva, so:
- Keep code simple, readable, and well commented. No clever one-liners.
- Follow Dragon Book (Aho, Lam, Sethi, Ullman) algorithms and terminology
  (closure, GOTO, canonical collection, ACTION/GOTO table, handle, lookahead).
- Python 3, standard library only, plus `graphviz` for diagrams.
- Console output first; a GUI only at the very end if I ask.

## Existing code to reuse (in labs/)
- labs/4.6-slr_parser.py: my SLR parser (LR0Item, closure, goto, table, parse trace).
  Problems: grammar is hardcoded, FOLLOW sets are hand-written, epsilon rules break
  (items use [] but rules use ["epsilon"], so rules.index() fails).
- labs/4.4-top_down_ll1_parser.py: compute_first, compute_follow, first_of_sequence. Reuse these.
- labs/4.2-*.py: parse_grammar_input() for "A -> x | y" format, Graphviz tree rendering.
- labs/3.4-transition_diagram.py: DFA-based lexer and Graphviz .dot generation.

## Grammar input format
One rule per line: `E -> E + T | T`. Symbols separated by spaces.
`epsilon` means empty. Non-terminals = any symbol appearing on a left-hand side.
The first rule's LHS is the start symbol. Lines starting with # are comments.

## Target structure
lr_parser/
  grammar.py      # parse grammar file, augment, symbols, FIRST/FOLLOW
  lr0.py          # LR(0) items, closure, goto, canonical collection
  lr1.py          # LR(1) items with lookaheads (CLR)
  tables.py       # build LR(0), SLR, CLR, LALR tables + conflict detection
  parser.py       # table-driven parse with trace, parse tree, error messages
  lexer.py        # turns real input like "a + 10 * b" into tokens (id, num, ...)
  visualize.py    # Graphviz: automaton diagram, parse tree
  main.py         # CLI menu
grammars/         # demo grammar files
tests/            # test cases

## Rules for working
- Work ONLY on the phase I ask for. Don't build ahead.
- After each phase, run the code on the demo grammars and show me the output.
- Explain briefly what you built and which Dragon Book algorithm it follows.

## Phase plan (follow this order)
1. Grammar input, augmentation, FIRST/FOLLOW ✅
2. LR(0) items, SLR table, conflict detection ✅
3. Table-driven parsing: trace, parse tree (Graphviz), error messages with expected tokens
4. Visualization of the LR(0) automaton (Graphviz) + lexer from labs/3.4
5. CLR(1) with LR(1) items, then LALR(1) by merging states with the same core
6. LR(0) table option, CLI menu, step-by-step mode, comparison table
7. Tests for all grammars + viva guide