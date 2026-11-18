# Viva guide: 30 likely questions

Short answers based on this project's code. Each answer names the file and function
that implements the idea. "DB" = Dragon Book, 2nd edition.

Quick map of the code:

| File | Main functions |
|---|---|
| `grammar.py` | `parse_grammar_lines`, `parse_precedence_lines`, `Grammar` (augmenting), `compute_first`, `first_of_sequence`, `compute_follow` |
| `lexer.py` | `TransitionDiagram` (`step`, `run`), `build_diagrams`, `tokenize` |
| `lr0.py` | `LR0Item`, `closure`, `goto`, `canonical_collection` |
| `lr1.py` | `LR1Item`, `closure_lr1`, `goto_lr1`, `canonical_lr1_collection`, `state_core`, `merge_lalr_states` |
| `tables.py` | `add_action`, `build_lr0_table`, `build_slr_table`, `build_lr1_table`, `build_parsing_table`, `find_conflicts`, `explain_conflicts`, `mark_conflicts_created_by_merging`, `apply_precedence`, `compare_methods` |
| `parser.py` | `parse`, `parse_text`, `choose_action`, `expected_terminals`, `rightmost_derivation`, `reductions_before_error`, `print_trace_step_by_step` |
| `visualize.py` | `automaton_graph`, `parse_tree_graph`, `draw_automaton`, `draw_parse_tree` |
| `main.py` | `run_menu` |

---

## A. Basics

**1. What does your project do, and how do you know it is correct?**
It takes any grammar from a text file and builds the LR(0), SLR(1), LALR(1) and CLR(1)
parsing tables. It explains every conflict, parses input with a full trace, and draws the
automaton and the parse tree. To check correctness, the 128 tests compare the output with
the Dragon Book: the 12 states and the edges of Fig. 4.31, every cell of Fig. 4.37, the
14-move trace of Fig. 4.38, the 10 LR(1) states of Fig. 4.41, and the CLR and LALR tables
of Figs. 4.42 and 4.43.
*Code:* `tests/` (for example `test_lr0_slr.py`, `test_parser.py`, `test_lr1_lalr.py`).

**2. What is a handle, and how does your parser find it?**
A handle is the right-hand side of a production that matches the top of the stack, where
reducing it is one step of the rightmost derivation in reverse. The parser never searches
for the handle. The state on top of the stack already knows: when `ACTION[s, a] = rN`,
the top |β| symbols are the handle for production N. `parse` pops exactly |β| states and
tree nodes, and the step-by-step explanation prints "pop 3 symbol(s) 'T * F' (the handle)".
*Code:* `parser.py`, `parse`, the reduce branch.

**3. Why do you augment the grammar with S' → S?**
It gives exactly one accept situation: the item `S' → S ·` with `$` as the next token. The
parser accepts only when the whole input has been reduced to S, never when an S appears
in the middle. If the name S' is already taken (epsilon.txt has `E'`), primes are added
until the name is new, so there it becomes `E''`. The new production is number (0), so the
user's rules are numbered from (1), as in the book.
*Code:* `grammar.py`, `Grammar.__init__` (step 4) and `make_augmented_name`.

**4. How do you store ε, and what was the ε bug in your old lab code?**
`A -> epsilon` is stored as `("A", [])`, a production with an empty body. In labs/4.6,
items used `[]` but the rule list used `["epsilon"]`, so `rules.index()` failed when it
tried to reduce. Now every item stores `prod_index`, the number of its production, and a
reduce uses that number directly. The only item of an ε rule is `A -> ·`, which is complete
(a reduce item) right away. When the parser reduces it, it pops nothing, and in the tree
A gets a single `ε` child.
*Code:* `grammar.py`, `parse_grammar_lines`; `lr0.py`, `LR0Item`; `parser.py`, `parse`.

## B. FIRST and FOLLOW

**5. How do you compute FIRST?**
Using DB §4.4.2, repeated until nothing changes (a fixed point):
- **Terminals:** FIRST(a) = {a}.
- **A production A → Y1…Yk:** FIRST(A) gets FIRST(Y1) minus ε. If Y1 can derive ε, it also
  gets FIRST(Y2) minus ε, and so on.
- **When everything can vanish:** if all of Y1…Yk can derive ε (or the body is empty),
  ε is added to FIRST(A).

All of this is in `first_of_sequence`, so `compute_first` only adds FIRST(body) to FIRST(A)
for every production.
*Code:* `grammar.py`, `compute_first` and `first_of_sequence` (adapted from labs/4.4).

**6. How do you compute FOLLOW? Why is $ in FOLLOW(S')?**
There are three rules:
1. `$` goes into FOLLOW of the start symbol.
2. For A → αBβ, FOLLOW(B) gets FIRST(β) minus ε.
3. If β is empty or can derive ε, FOLLOW(B) also gets FOLLOW(A).

The loop repeats until nothing changes. Rule 1 is applied to the augmented start S', and
FOLLOW(S) then gets `$` through rule 3 applied to S' → S. For expr.txt:
FOLLOW(E) = {+, ), $} and FOLLOW(T) = FOLLOW(F) = {+, *, ), $}, as in DB Example 4.30.
*Code:* `grammar.py`, `compute_follow`.

**7. Where else do you use FIRST of a string of symbols?**
- **FOLLOW rules 2 and 3:** FIRST(β), with β being the symbols after B.
- **LR(1) closure:** FIRST(βa), which gives the lookaheads of the new items.

The same function serves both, and it handles an empty list (returns {ε}).
*Code:* `grammar.py`, `first_of_sequence`; used in `compute_follow` and `lr1.py`, `closure_lr1`.

## C. Items, CLOSURE, GOTO

**8. What is an LR(0) item? What are kernel items?**
An item is a production with a dot in its body, such as `E -> E · + T`. Left of the dot is
what is already on the stack; right of it is what we still expect. Kernel items are
`S' -> · S` plus every item whose dot is not at the left end. The other items (dot at the
left end) are added by CLOSURE and can always be recomputed from the kernel. The drawing
shows closure items in grey, below a line.
*Code:* `lr0.py`, `LR0Item` (`next_symbol`, `advance`, `is_complete`, `is_kernel`).

**9. How does CLOSURE work? Walk through I0 of the expression grammar.**
If the dot is before a non-terminal B, we expect to see a B, so we add `B -> · γ` for
every production of B (DB Fig. 4.32). The code keeps a list and an index `i` that walks
along it while it grows, so every item is examined once. For I0:
1. Start with `E' -> · E`.
2. E is after the dot, so add `E -> · E + T` and `E -> · T`.
3. T is after the dot, so add `T -> · T * F` and `T -> · F`.
4. F is after the dot, so add `F -> · ( E )` and `F -> · id`.

That gives 7 items. The check `if new_item not in result` stops the left-recursive
`E -> · E + T` from adding items forever.
*Code:* `lr0.py`, `closure`.

**10. How does GOTO work? Why is GOTO(I0, E) = I1?**
GOTO(I, X) means "which state do we move to after seeing X in state I?". It takes the items
with X after the dot, moves the dot over X, and takes the closure.
- **In I0, the items with E after the dot** are `E' -> · E` and `E -> · E + T`.
- **Moving the dot** gives `E' -> E ·` and `E -> E · + T`.
- **The closure adds nothing,** because nothing after the dot is a non-terminal.

That set is I1.
*Code:* `lr0.py`, `goto`.

**11. How do you build the canonical collection, and how do you know a state is new?**
DB Fig. 4.33: start with CLOSURE({S' → ·S}). Then, for each state in order and each grammar
symbol, compute GOTO. If the result is new, append it, and always record the transition
`(i, X) -> j`. A state is a *set*, so its items are compared as a `frozenset`, where order
doesn't matter, and that frozenset is used as a dictionary key. Non-terminals are tried
before terminals, which numbers the states exactly as in Fig. 4.31.
*Code:* `lr0.py`, `canonical_collection` (`lr1.py`, `canonical_lr1_collection` is the same loop).

**12. What does the LR automaton recognize?**
Viable prefixes: the stack contents that can appear while parsing a correct input, i.e.
prefixes of right-sentential forms that do not go past the end of the handle. It is a DFA
whose alphabet is the grammar symbols and whose states are sets of items. The parser uses
it to know when the top of the stack is a handle.
*Code:* `visualize.py`, `automaton_graph` draws it (for example `report/figures/expr_slr_automaton.png`).

## D. Tables and conflicts

**13. How do you build the SLR(1) table?**
DB Algorithm 4.46. For every state i and every item in it:
- (a) `A -> α · a β` with a terminal a: shift, `ACTION[i, a] = s j`, where j = GOTO(i, a).
- (b) `A -> α ·`: reduce, `r n` on every terminal in FOLLOW(A).
- (c) `S' -> S ·`: `ACTION[i, $] = acc`.

Transitions on non-terminals become the GOTO table.
*Code:* `tables.py`, `build_slr_table`.

**14. What is the difference between LR(0) and SLR(1)?**
Both use the same LR(0) states. LR(0) reduces on **every** terminal, because it does not
look at the next token at all. SLR reduces only on FOLLOW(A). For expr.txt, LR(0) has
conflicts in states 2 (`E -> T ·`, `T -> T · * F`) and 9, both on `*`. SLR has none,
because `*` is not in FOLLOW(E).
*Code:* `tables.py`, `build_lr0_table` and `build_slr_table`; `report/figures/expr_lr0_automaton.png`.

**15. How do you detect conflicts and tell their kind?**
The table is never overwritten. `add_action` stores each cell as a dictionary
`{action: [(item, reason), ...]}`, so a cell with two or more actions is a conflict.
`find_conflicts` checks every cell:
- **shift-reduce:** the cell has a shift and a reduce.
- **reduce-reduce:** the cell has two or more reduces.

`explain_conflicts` prints the state, the input symbol, and each action with the item that
caused it and why.
*Code:* `tables.py`, `add_action`, `find_conflicts`, `explain_conflicts`.

**16. Why does state 2 of slr_conflict.txt (grammar 4.49) have a shift-reduce conflict?**
I2 = { `S -> L · = R`, `R -> L ·` }.
- **The first item** shifts on `=`.
- **The second item** reduces on FOLLOW(R) = {=, $}. `=` gets into FOLLOW(R) because
  `S → L = R` puts `=` in FOLLOW(L), and `L → * R` copies FOLLOW(L) into FOLLOW(R).

So cell [2, =] gets s6 and r5. In state 2 the L was read at the start of the sentence, and
no right-sentential form starts with `R =`, so the reduce is never right. SLR adds it anyway
because FOLLOW is one set for the whole grammar. The grammar is not ambiguous: in CLR the
item is `[R -> L ·, $]`, which reduces only on `$`, so there is no conflict.
*Code:* `tables.py`, `build_slr_table` and `explain_conflicts`; `report/figures/slr_conflict_slr_automaton.png`.

## E. The parser

**17. Explain your parsing loop.**
DB Algorithm 4.44. There is a state stack (it starts with 0), a stack of tree nodes (their
symbols are the SYMBOLS column), and the input with `$` at the end. Then repeat:
- **Look up** `ACTION[s, a]`, where s is the top state and a the current token.
- **Shift t:** push t and a leaf, and move to the next token.
- **Reduce A → β:** pop |β| states and nodes, look at the state t now on top, and push
  `GOTO[t, A]` and a new node A with the popped nodes as its children.
- **acc:** stop and accept.
- **Empty cell:** syntax error.

The parser only reads the table, so the same code runs all four methods.
*Code:* `parser.py`, `parse`.

**18. How is the parse tree built? What is the `[-0:]` trap?**
A shift pushes a leaf, which also keeps the lexeme, e.g. `id (count)`. A reduce pops |β|
nodes and makes them the children of a new node A, so the tree is built bottom-up, exactly
in the order of the reductions. Nodes are popped one at a time in a loop. `list[-k:]` would
be wrong for an ε rule: there k = 0, and `list[-0:]` is the **whole** list. An ε rule gives
A one `ε` child instead.
*Code:* `parser.py`, `ParseTreeNode` and the reduce branch of `parse`.

**19. Why do the reductions in reverse order give a rightmost derivation?**
A bottom-up parser reverses a rightmost derivation (DB §4.5): each reduction undoes one
`=>rm` step. So `rightmost_derivation` starts from S and applies the productions in
reverse order of the reductions, each time replacing the **rightmost** non-terminal. For
`id * id + id` it prints E ⇒ E + T ⇒ E + F ⇒ E + id ⇒ T + id ⇒ … ⇒ id * id + id.
*Code:* `parser.py`, `rightmost_derivation`.

**20. How do you report a syntax error?**
An empty `ACTION[s, a]` cell is an error. The message gives:
- **where:** the line and column of the token (from the lexer), and its number in the input
- **what:** the unexpected token, or "unexpected end of input"
- **which state** the parser was in
- **what was expected:** the terminals that have an entry in that state's ACTION row

Before parsing starts, every token kind is also checked against the grammar's terminals,
for example "`num` is not a terminal of this grammar".
*Code:* `parser.py`, `parse` (error branch) and `expected_terminals`.

## F. LR(1), CLR and LALR

**21. What is an LR(1) item, and what does the lookahead mean?**
`[A -> α · β, a]` is an LR(0) item plus a terminal `a`. It means: after this A is
complete, the next token must be `a`. The lookahead is copied unchanged when the dot moves,
and it only matters when the dot is at the end: `[A -> α ·, a]` reduces only on `a`.
In general an item's lookaheads are a subset of FOLLOW(A), so CLR reduces in fewer places
than SLR.
*Code:* `lr1.py`, `LR1Item` (it extends `LR0Item`; equality includes the lookahead,
`core()` leaves it out).

**22. Why do the new items in LR(1) closure get lookaheads FIRST(βa)?**
For `[A -> α · B β, a]`: after B is reduced, the parser will see β next, and if β can
vanish it will see `a`. So every `B -> · γ` gets each b in FIRST(βa) as its lookahead.
In cc.txt, `[S -> · C C, $]` gives the C-items FIRST(C $) = {c, d}, which is why I0 has
`[C -> · c C, c/d]`. Because `a` is a terminal, FIRST(βa) never contains ε.
*Code:* `lr1.py`, `closure_lr1`, the call `first_of_sequence(beta + [item.lookahead], ...)`.

**23. Why does CLR have more states than SLR?**
States with the same LR(0) items but different lookaheads are kept apart. In cc.txt, I3
and I6 both have the core `C -> c · C`: I3 is for the first C (lookaheads c/d) and I6 for
the second C (lookahead $). Some numbers from this project:
- **cc.txt:** 10 states in CLR, 7 in LR(0)
- **expr.txt:** 22 states in CLR, 12 in LR(0)
- **slr_conflict.txt:** 14 states in CLR, 10 in LR(0)

This splitting is where CLR's precision comes from, and it is also why real CLR tables
get very large.
*Code:* `lr1.py`, `canonical_lr1_collection`; `report/figures/cc_clr_automaton.png`.

**24. How do you build LALR(1)?**
DB Algorithm 4.59, in three steps:
1. Build the LR(1) collection.
2. Group the states by **core**, the set of their LR(0) items, and merge each group into one
   state with all the lookaheads combined.
3. Map every transition to the merged states. This is well defined, because states with the
   same core have GOTOs with the same core.

The table is then built with the same function as CLR. `merged_from` records which LR(1)
states went into each LALR state. For cc.txt, I3+I6, I4+I7 and I8+I9 are merged, giving
7 states, as in Fig. 4.43. LALR always has exactly as many states as LR(0), which a test
checks for every grammar. Yacc and Bison build LALR tables.
*Code:* `lr1.py`, `state_core` and `merge_lalr_states`; `tables.py`, `build_parsing_table`
(case "lalr") and `build_lr1_table`.

**25. Can merging states create conflicts?**
**Reduce-reduce: yes.** In lalr_conflict.txt, the LR(1) states I6 = {`[A→c·, d]`, `[B→c·, e]`}
and I9 = {`[A→c·, e]`, `[B→c·, d]`} have the same core. Each is fine on its own. Merged,
A → c and B → c both reduce on `d` and on `e`.
**Shift-reduce: no.** Suppose the merged state had a shift on `a` and a reduce `[A→α·, a]`.
The reduce item came from one of the original states. That state has the same core, so it
also had the shift on `a`. The conflict therefore already existed in CLR.
The program marks such conflicts as "Created by merging LR(1) states I6, I9" and shows
which state each item came from.
*Code:* `tables.py`, `mark_conflicts_created_by_merging`; `report/figures/lalr_conflict_lalr_automaton.png`.

**26. How do LR(0), SLR, LALR and CLR compare?**
In what they can handle: LR(0) ⊂ SLR(1) ⊂ LALR(1) ⊂ CLR(1). In size: LR(0) = SLR = LALR
states, fewer than CLR. The comparison report has a demo grammar for every step:
- **cc.txt** is LR(0).
- **expr.txt** is SLR but not LR(0).
- **slr_conflict.txt** is LALR but not SLR.
- **lalr_conflict.txt** is CLR but not LALR.
- **The ambiguous grammars** have conflicts under every method.

*Code:* `tables.py`, `compare_methods` and `print_comparison_summary`; `report/figures/comparison.txt`.

**27. Which method detects errors earliest?**
All four report the error at the **same token**, and none of them ever shifts a wrong
token. SLR and LALR may first make some reductions that turn out to be useless, because
their reduce lookaheads (FOLLOW, or merged lookaheads) are larger than needed. CLR's
lookaheads are exact, so it reports the error immediately. Two examples:
- **`c c d` in cc.txt:** CLR stops in state 4 with 0 reductions. SLR and LALR first reduce
  C → d and C → c C twice (3 reductions).
- **`id )` in expr.txt:** CLR makes 0 reductions against 3, and its expected tokens are
  more precise (`+, *, $` instead of `+, $`).

*Code:* `parser.py`, `reductions_before_error`; `report/figures/error_detection_cc.txt`.

## G. Ambiguity, precedence, lexer

**28. Can an ambiguous grammar be LR? What happens with the dangling else?**
No. An ambiguous grammar always has a conflict under every LR method. In dangling_else.txt,
after `i E t S` with `e` next, the parser can reduce `S → i E t S` (if-without-else) or
shift `e`. With `--resolve` the parser uses Yacc's default choice, which is to shift on a
shift-reduce conflict (and take the earliest production on a reduce-reduce conflict).
Shifting gives each `else` to the **nearest** `if`, as in C. The trace marks the choice,
e.g. `[conflict ...: chose s… (prefer shift)]`.
*Code:* `parser.py`, `choose_action`; `report/figures/dangling_else_parse_tree.png`.

**29. How do precedence and associativity resolve conflicts?**
DB §4.8.1. `%left +` then `%left *` gives `+` level 1 and `*` level 2 (later lines bind
tighter). A production takes the precedence of its **rightmost terminal**, so E → E + E
has level 1. For a cell with "shift a" and "reduce by p":
- **a binds tighter than p:** shift
- **p binds tighter than a:** reduce
- **equal:** `%left` reduces, `%right` shifts, `%nonassoc` empties the cell (an error)

In state 7 (`E → E + E ·`) with `*` next, `*` binds tighter, so the parser shifts and
builds id + (id * id). With `+` next, the levels are equal and `+` is left-associative, so
it reduces, giving (id + id) + id. Without precedence, Yacc's "always shift" builds the
**wrong** tree for `id * id + id`: id * (id + id). Precedence never resolves
reduce-reduce conflicts.
*Code:* `grammar.py`, `parse_precedence_lines` and `production_precedence`; `tables.py`,
`apply_precedence`; `report/figures/precedence_id_plus_id_times_id.txt`.

**30. Why are the lexer and parser separate? How do the lexer's tokens match the grammar?**
- **Different levels:** the lexer works on characters with DFAs (transition diagrams from
  labs/3.4), which recognize regular languages. The parser works on tokens with the LR
  automaton, which handles context-free languages. Keeping them apart keeps both simple.
- **Retracting:** an identifier ends when a non-letter/digit is read, and the lexer then
  moves back one character (the `*` states of DB §3.4).
- **Token kind:** identifier → `id`, number → `num`, an operator → the operator itself.
- **Reserved words:** an identifier whose text is a terminal of the grammar (like `if`)
  keeps that word as its kind (DB §3.4.3).
- **Kept for later:** every token keeps its lexeme, line and column, for error messages
  and for tree leaves such as `id (count)`.

*Code:* `lexer.py`, `TransitionDiagram.run`, `build_diagrams` and `tokenize`; `parser.py`, `parse_text`.
