# 5-minute demo script

The story of the demo: **one parser, four ways to build its table, and why the stronger
methods exist.** Each step shows one idea, and each idea is a Dragon Book algorithm.

## Before the demo (not timed)

- [ ] Open a PowerShell terminal in the project folder, maximized, with a large font.
- [ ] `dot -V` works (Graphviz on PATH). If not, use the ready-made pictures in `report/figures/`.
- [ ] Run once: `python -m unittest discover -s tests`. It should end with `Ran 128 tests ... OK`.
- [ ] Draw the pictures in advance, so the demo needs no waiting:
  ```
  python lr_parser/visualize.py grammars/expr.txt
  python lr_parser/visualize.py grammars/slr_conflict.txt
  python lr_parser/visualize.py grammars/cc.txt --method clr
  python lr_parser/visualize.py grammars/cc.txt --method lalr
  ```
- [ ] Have `docs/viva_guide.md` open in another window for the questions afterwards.

---

## 0:00–0:20 Introduction

**Say:** "My project is an LR parser generator. You give it any grammar in a text file,
and it builds the LR(0), SLR, LALR and canonical LR tables, explains every conflict,
parses input with a full stack trace, and draws the automaton and the parse tree.
Everything follows the Dragon Book, and 128 tests check it against the book's figures."

## 0:20–0:50 Step 1: grammar, augmentation, FIRST and FOLLOW

```
python lr_parser/grammar.py grammars/epsilon.txt
```
**Show:** production (0) `E'' -> E`, the rules `E' -> ε`, and `FIRST(E') = { +, ε }`.

**Say:** "The grammar is augmented with a new start production. E' was already taken, so
it is called E''. An ε rule is stored as an empty list; that fixed the ε bug in my old lab
code. FIRST and FOLLOW are computed by repeating the book's rules until nothing changes,
and they match Example 4.30."

## 0:50–1:30 Step 2: the LR(0) automaton (CLOSURE and GOTO)

```
start output\expr_slr_automaton.png
```
**Show:** I0 with its kernel item above the line and the closure items in grey; the
edge E from I0 to I1; the green accept state.

**Say:** "Each box is a set of LR(0) items. I0 is CLOSURE of E' → ·E: because the dot is
before E, we add the E-productions, then the T- and F-productions. GOTO(I0, E) moves the
dot over E and gives I1. These 12 states are exactly Figure 4.31."

## 1:30–2:30 Step 3: the SLR table and parsing, step by step

```
python lr_parser/parser.py grammars/expr.txt "id * id + id" --step
```
**Do:** press Enter 3 times, then type `r` and Enter.
**Show:** the STACK / SYMBOLS / INPUT / ACTION columns; the explanation under a reduce
("pop 1 symbol(s) 'id' (the handle) ... GOTO[0, F] = 3"); then the rightmost derivation
and the parse tree at the end.

**Say:** "The parser only reads the ACTION and GOTO table. On a reduce it pops the
handle, and GOTO tells it the new state. These 14 moves are Figure 4.38. Reading the
reductions backwards gives the rightmost derivation, so a bottom-up parser is a rightmost
derivation in reverse."

*(If short on time, leave out `--step`.)*

## 2:30–3:15 Step 4: why SLR is not enough

```
python lr_parser/tables.py grammars/slr_conflict.txt
```
**Show:** scroll to the end: `SHIFT-REDUCE conflict in state 2 on input '='`, with the two
items. Then `start output\slr_conflict_slr_automaton.png` and point at the red I2.

**Say:** "This is grammar 4.49. State 2 has S → L·=R, which shifts on =, and R → L·,
which SLR reduces on everything in FOLLOW(R), and = is in FOLLOW(R). But FOLLOW is one
set for the whole grammar. In this state the reduce can never be right, and the grammar
is not even ambiguous."

```
python lr_parser/tables.py grammars/slr_conflict.txt --method clr
```
**Show:** the last line, `No conflicts: the grammar is CLR(1).`

## 3:15–4:00 Step 5: CLR lookaheads and LALR merging

```
start output\cc_clr_automaton.png
start output\cc_lalr_automaton.png
```
**Show:** in the CLR picture, I3 `C -> c · C, c/d` and I6 `C -> c · C, $` (the same core,
different lookaheads). In the LALR picture, `I3 (= I3 + I6 of LR(1))`.

**Say:** "In CLR every item carries a lookahead, computed as FIRST of what follows. That
splits states: 10 states instead of 7, as in Figure 4.41. LALR merges the states with the
same core. That gives LR(0)'s 7 states but keeps per-state lookaheads, which is what Yacc
does. Merging can create reduce-reduce conflicts, but never shift-reduce ones; my
lalr_conflict grammar shows the reduce-reduce case."

## 4:00–4:25 Step 6: CLR detects errors sooner

```
python lr_parser/parser.py grammars/cc.txt "c c d" --method lalr
python lr_parser/parser.py grammars/cc.txt "c c d" --method clr
```
**Show:** the last line of each: `Reductions done before the error was detected: 3`,
then `0`.

**Say:** "Both find the error at the same token, but LALR first makes three useless
reductions. CLR's lookaheads are exact, so it stops immediately."

## 4:25–4:45 Step 7: ambiguous grammar plus precedence

```
python lr_parser/parser.py grammars/ambiguous_expr_prec.txt "id + id * id"
```
**Show:** the 4 resolved conflicts at the top (`'*' has higher precedence than E -> E + E`),
then the tree: `+` at the root and `id * id` under it.

**Say:** "E → E + E is ambiguous, so every method has conflicts. With %left + and
%left *, the conflicts are resolved the way Yacc does, and the tree is id + (id * id)."

## 4:45–5:00 Step 8: comparison and summary

```
python lr_parser/tables.py (Resolve-Path -Relative grammars\*.txt) --compare
```
**Show:** the summary grid at the end.

**Say:** "This grid shows the whole hierarchy: cc is LR(0), expr is SLR but not LR(0),
slr_conflict is LALR but not SLR, lalr_conflict is CLR but not LALR, and the ambiguous
grammars fit no class. Thank you; I'm happy to take questions."

---

## Backup plans

- **No Graphviz on the demo machine:** open the PNGs in `report/figures/` instead
  (same pictures).
- **A command fails or the terminal is slow:** show the matching text file in
  `report/figures/` (`trace_expr_id_times_id_plus_id.txt`, `error_detection_cc.txt`,
  `precedence_id_plus_id_times_id.txt`, `comparison.txt`).
- **Asked to "show everything in one place":** `python lr_parser/main.py grammars/expr.txt`
  opens the menu (options 2, 4, 5, 6, 7, 8, 10).
- **Asked for the code:** open the function named in `docs/viva_guide.md` for that topic.
