# LR Parser Generator & Visualizer

A teaching tool for **bottom-up LR parsing**. You give it a context-free grammar in a
text file; it builds the **LR(0), SLR(1), LALR(1) and CLR(1)** parsing tables,
finds and explains every conflict, parses input with a full stack trace, and draws
the LR automaton and the parse tree with Graphviz.

All algorithms follow the Dragon Book (Aho, Lam, Sethi, Ullman, *Compilers:
Principles, Techniques, and Tools*, 2nd ed., Chapter 4), and the results are checked
against the book's figures by the tests.

## What it does

| Feature | Dragon Book | Where |
|---|---|---|
| Read a grammar file, augment it with `S' -> S` | §4.6.2 | `grammar.py` |
| FIRST and FOLLOW sets (with ε rules) | §4.4.2 | `grammar.py` |
| LR(0) items, CLOSURE, GOTO, canonical LR(0) collection | Fig. 4.32, 4.33 | `lr0.py` |
| LR(0) and SLR(1) tables | Alg. 4.46 | `tables.py` |
| LR(1) items with lookaheads, canonical LR(1) collection | Fig. 4.40 | `lr1.py` |
| CLR(1) table | Alg. 4.56 | `tables.py` |
| LALR(1) by merging states with the same core | Alg. 4.59 | `lr1.py`, `tables.py` |
| Conflict detection and explanation (which state, which items, which kind) | §4.6.4, §4.7.4 | `tables.py` |
| Precedence and associativity (`%left`, `%right`, `%nonassoc`) | §4.8.1, §4.9.2 | `grammar.py`, `tables.py` |
| Table-driven LR parsing with a stack trace | Alg. 4.44, Fig. 4.38 | `parser.py` |
| Parse tree and rightmost derivation | §4.5 | `parser.py` |
| Syntax errors with position and expected tokens | §4.8.3 | `parser.py` |
| Lexer: real text such as `count + 10 * (x + y)` into tokens | §3.4 | `lexer.py` |
| Graphviz drawings of the automaton and the parse tree | | `visualize.py` |
| Interactive menu, step-by-step parsing, comparison report | | `main.py` |

## Installation

1. **Python 3.10 or newer** (developed with Python 3.13). No other Python
   packages are needed except:
2. **The `graphviz` Python package**:
   ```
   pip install -r requirements.txt
   ```
3. **The Graphviz program** (it draws the PNG files):
   - Windows: `winget install graphviz`, then add `C:\Program Files\Graphviz\bin`
     to your PATH and restart the terminal / VS Code. Check with `dot -V`.
   - Linux: `sudo apt install graphviz`. macOS: `brew install graphviz`.

   Without the Graphviz program everything else still works; drawings are then saved
   only as `.dot` text files, which you can paste into
   <https://dreampuf.github.io/GraphvizOnline>.

All commands below are run from the project folder.

## How to run

### Interactive menu (everything in one place)
```
python lr_parser/main.py
python lr_parser/main.py grammars/expr.txt        # start with a grammar loaded
```
The menu lets you load a grammar, show FIRST/FOLLOW, choose the method, show the item
sets and the table, parse input (all at once or step by step), draw the automaton and
the parse tree, and print the comparison report.

### Grammar, FIRST and FOLLOW
```
python lr_parser/grammar.py grammars/expr.txt grammars/epsilon.txt
```

### Item sets, parsing table and conflicts
```
python lr_parser/tables.py grammars/expr.txt                       # SLR(1) (default)
python lr_parser/tables.py grammars/cc.txt --method clr            # lr0 | slr | lalr | clr
python lr_parser/tables.py grammars/lalr_conflict.txt --method lalr
```
LALR prints which LR(1) states were merged, and marks conflicts that merging created.

### Comparison of all four methods
```
python lr_parser/tables.py grammars/*.txt --compare
```
(In PowerShell, list the files instead of `*.txt`, or use menu option 10.)

### Parsing
```
python lr_parser/parser.py grammars/expr.txt "id * id + id"
python lr_parser/parser.py grammars/expr_num.txt "count + 10 * (x + y)" --method lalr
python lr_parser/parser.py grammars/expr.txt "id * id + id" --step          # one move per Enter
python lr_parser/parser.py grammars/cc.txt "c c d" --method clr             # an error
python lr_parser/parser.py grammars/dangling_else.txt "i b t i b t a e a" --resolve
```
Options: `--method lr0|slr|lalr|clr`, `--step` (step-by-step mode), `--resolve`
(parse even with conflicts, using Yacc's default choices), `--out NAME` (output file name).
The output shows the tokens, the trace (STACK, SYMBOLS, INPUT, ACTION as in Figure 4.38),
the productions used, the rightmost derivation and the parse tree, and saves
`output/<grammar>_parse_tree.png`.

### Drawing the automaton
```
python lr_parser/visualize.py grammars/expr.txt                 # LR(0) automaton (Figure 4.31)
python lr_parser/visualize.py grammars/cc.txt --method clr      # LR(1) automaton with lookaheads
python lr_parser/visualize.py grammars/cc.txt --method lalr     # merged LALR(1) automaton
```
Saved as `output/<grammar>_<method>_automaton.png`. States with conflicts are red, and the
accept state is green.

### Lexer only
```
python lr_parser/lexer.py "count + 10 * (x + y)"
```

### Tests
```
python -m unittest discover -s tests
```
128 tests. They check the results against Dragon Book Figures 4.31, 4.37, 4.38, 4.41,
4.42 and 4.43 and Examples 4.30, 4.45 and 4.48.

## Grammar file format

```
# comment
%left +          (optional precedence lines; later lines bind tighter)
%left *
E -> E + T | T
T -> T * F | F
F -> ( E ) | id
```
- One rule per line, symbols separated by spaces, alternatives separated by `|`.
- `epsilon` means the empty string.
- Non-terminals are the symbols that appear on a left-hand side; everything else is a
  terminal. The first rule's left-hand side is the start symbol.
- `%left`, `%right` and `%nonassoc` are optional and only used to resolve conflicts
  (Dragon Book §4.8.1).

The lexer turns input text into these terminals: identifiers become `id`, numbers
become `num`, operators and punctuation stand for themselves (`+`, `(`, `<=`, ...), and a
word that is itself a terminal of the grammar (like `if`) stays that word.

## Demo grammars (`grammars/`)

| File | Grammar | Dragon Book | Result |
|---|---|---|---|
| `cc.txt` | S → C C, C → c C \| d | grammar 4.55, Fig. 4.41–4.43 | LR(0); CLR 10 states, LALR 7 |
| `expr.txt` | E → E + T \| T, ... | grammar 4.1, Fig. 4.31, 4.37 | SLR(1), not LR(0) |
| `expr_num.txt` | expr.txt + `F → num` | | SLR(1), for real input through the lexer |
| `epsilon.txt` | E → T E', E' → + T E' \| ε, ... | grammar 4.28, Example 4.30 | SLR(1), has ε rules |
| `slr_conflict.txt` | S → L = R \| R, L → * R \| id, R → L | grammar 4.49, Example 4.48 | LALR(1), not SLR(1) |
| `lalr_conflict.txt` | S → a A d \| b B d \| a B e \| b A e, A → c, B → c | §4.7.4 | CLR(1), not LALR(1) |
| `reduce_reduce.txt` | S → A \| B, A → a, B → a | | not LR(1) (ambiguous) |
| `dangling_else.txt` | S → i E t S \| i E t S e S \| a | §4.8.2 | not LR(1) (ambiguous) |
| `ambiguous_expr.txt` | E → E + E \| E * E \| ( E ) \| id | grammar 4.3, §4.8.1 | not LR(1) (ambiguous) |
| `ambiguous_expr_prec.txt` | the same + `%left +`, `%left *` | §4.8.1 | conflicts resolved by precedence |

The comparison report shows the hierarchy LR(0) ⊂ SLR(1) ⊂ LALR(1) ⊂ CLR(1): for each
step there is a grammar that belongs to the stronger class but not to the weaker one
(see `report/figures/comparison.txt`).

## Project structure

```
lr_parser/
  grammar.py      read grammar, augment, FIRST/FOLLOW, precedence declarations
  lexer.py        transition-diagram lexer (from labs/3.4): text -> tokens
  lr0.py          LR(0) items, CLOSURE, GOTO, canonical LR(0) collection
  lr1.py          LR(1) items, CLOSURE, GOTO, canonical LR(1) collection, LALR merging
  tables.py       LR(0)/SLR/LALR/CLR tables, conflicts, precedence, comparison report
  parser.py       table-driven LR parser: trace, parse tree, derivation, errors, step mode
  visualize.py    Graphviz: automaton and parse tree
  main.py         interactive menu
grammars/         demo grammars (table above)
tests/            unittest tests (128)
docs/
  viva_guide.md   30 likely viva questions with answers
  demo_script.md  5-minute demo plan
report/figures/   PNG figures and text outputs for the report
labs/             earlier lab code that this project grew from
output/           generated drawings (not in git)
```

The modules depend on each other in one direction:
`grammar → lr0 → lr1 → tables → parser → main`, with `lexer` used by `parser` and
`visualize` used by `parser` and `main`.
