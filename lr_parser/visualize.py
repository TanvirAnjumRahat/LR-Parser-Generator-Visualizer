"""
visualize.py - Graphviz drawings.

  - automaton_graph(): the LR(0) automaton, drawn like Dragon Book Figure 4.31.
                       Each state is a box: its name, the kernel items, a line,
                       then the closure items (in grey). Edges are labeled with
                       the GOTO symbol. The accept state is green and has a
                       "$ -> accept" edge; states with conflicts are red.
  - parse_tree_graph(): the parse tree (based on render_parse_tree() in labs/4.2).
  - save_graph():      writes output/<name>.dot, and output/<name>.png if the
                       Graphviz program "dot" is installed.

Files are named after the grammar (e.g. expr_automaton.png,
expr_parse_tree.png) so runs on different grammars don't overwrite each other.
"""

import html
import os
import sys

import graphviz

from lr1 import LR1Item, group_by_core, item_group_text

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")


def output_base_name(grammar_file, out_option=None):
    """
    The prefix for output files: the --out value if given, otherwise the
    grammar file name without folder and extension ("grammars/expr.txt" -> "expr").
    """
    if out_option:
        return out_option
    file_name = os.path.basename(grammar_file)
    return os.path.splitext(file_name)[0]


def save_graph(graph, name, out_dir=OUTPUT_DIR):
    """
    Save the DOT source as <out_dir>/<name>.dot and try to render <name>.png.
    Returns the path of the PNG, or of the .dot file if 'dot' is not installed.
    """
    os.makedirs(out_dir, exist_ok=True)
    base_path = os.path.join(out_dir, name)
    dot_path = graph.save(base_path + ".dot")

    try:
        png_path = graph.render(base_path, format="png", cleanup=True)
    except graphviz.ExecutableNotFound:
        print(f"Saved DOT source: {dot_path}")
        print("  (No PNG: the Graphviz program 'dot' is not on PATH. Add")
        print("   C:\\Program Files\\Graphviz\\bin to PATH, or open the .dot file in")
        print("   an online viewer such as https://dreampuf.github.io/GraphvizOnline)")
        return dot_path

    print(f"Drawn: {png_path}")
    return png_path


# ----------------------------------------------------------------------
# LR(0) automaton
# ----------------------------------------------------------------------

def html_text(text):
    """Escape <, >, & so item text like 'E -> · E' is safe inside an HTML-like label."""
    return html.escape(text, quote=False)


def accept_state_number(grammar, states):
    """The state containing S' -> S ·  (where the parser accepts on $)."""
    for i in range(len(states)):
        for item in states[i]:
            if item.lhs == grammar.augmented_start and item.is_complete():
                return i
    return None


def item_lines(grammar, items):
    """
    The text lines to show for a state, as (text, is_kernel) pairs.
      LR(0) items: one line per item, e.g.  E -> E · + T
      LR(1) items: items with the same core share one line with all their
                   lookaheads, as in the book, e.g.  C -> c · C, c/d
    """
    lines = []
    if items and isinstance(items[0], LR1Item):
        for item, lookaheads in group_by_core(grammar, items):
            lines.append((item_group_text(item, lookaheads), item.is_kernel(grammar)))
    else:
        for item in items:
            lines.append((str(item), item.is_kernel(grammar)))
    return lines


def state_label(grammar, i, items, is_accept, has_conflict, merged_from=None):
    """
    Build the HTML-like label of one state: a small table with
      row 1     : the state name (I0, I1, ...)
      next rows : kernel items
      a line    : <HR/>
      next rows : closure items, in grey
    merged_from: for LALR, the LR(1) states this state was merged from.
    """
    title = f"I{i}"
    if merged_from is not None and len(merged_from) > 1:
        title += "  (= " + " + ".join(f"I{j}" for j in merged_from) + " of LR(1))"
    border_color = "black"
    background = "white"
    if is_accept:
        title += "  (accept)"
        background = "#d9f2d9"     # light green
    if has_conflict:
        title += "  (conflict)"
        border_color = "red"
        background = "#fde0e0"     # light red

    kernel = []
    closure_lines = []
    for text, is_kernel in item_lines(grammar, items):
        if is_kernel:
            kernel.append(text)
        else:
            closure_lines.append(text)

    rows = []
    rows.append(f'<TR><TD><B>{html_text(title)}</B></TD></TR>')
    for text in kernel:
        rows.append(f'<TR><TD ALIGN="LEFT">{html_text(text)}</TD></TR>')
    if closure_lines:
        rows.append("<HR/>")
        for text in closure_lines:
            rows.append(f'<TR><TD ALIGN="LEFT"><FONT COLOR="#666666">'
                        f'{html_text(text)}</FONT></TD></TR>')

    table = (f'<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3" '
             f'COLOR="{border_color}" BGCOLOR="{background}">'
             + "".join(rows) + "</TABLE>")
    # The extra < > around the table tell Graphviz this is an HTML-like label.
    return "<" + table + ">"


def automaton_graph(grammar, states, transitions, conflict_states=None, title=None,
                    merged_from=None):
    """
    Build the Graphviz graph of an LR automaton: LR(0) (for SLR), LR(1) (for CLR)
    or the merged LALR(1) one - the states decide which.
    conflict_states: set of state numbers to draw in red (from the parsing table).
    merged_from    : LALR only, merged_from[k] = LR(1) states merged into state k.
    """
    if conflict_states is None:
        conflict_states = set()
    accept_state = accept_state_number(grammar, states)

    graph = graphviz.Digraph("automaton")
    graph.attr("graph", rankdir="LR", fontname="Helvetica")
    graph.attr("node", shape="plaintext", fontname="Helvetica", fontsize="11")
    graph.attr("edge", fontname="Helvetica", fontsize="11")
    if title:
        graph.attr("graph", label=title, labelloc="t")

    # An arrow pointing at the start state I0
    graph.node("start", label="start", shape="none")
    graph.edge("start", "I0")

    # One box per state
    for i in range(len(states)):
        group = None
        if merged_from is not None:
            group = merged_from[i]
        label = state_label(grammar, i, states[i],
                            is_accept=(i == accept_state),
                            has_conflict=(i in conflict_states),
                            merged_from=group)
        graph.node(f"I{i}", label=label)

    # One edge per GOTO transition, labeled with the symbol
    for (i, X), j in transitions.items():
        graph.edge(f"I{i}", f"I{j}", label="<" + html_text(X) + ">")

    # Like Figure 4.31: the accept state goes to "accept" on $
    if accept_state is not None:
        graph.node("accept", label="accept", shape="none", fontcolor="darkgreen")
        graph.edge(f"I{accept_state}", "accept", label="$")

    return graph


# ----------------------------------------------------------------------
# Parse tree
# ----------------------------------------------------------------------

def parse_tree_graph(grammar, root):
    """
    Build the Graphviz graph of a parse tree.
      non-terminals : ellipses
      terminals     : boxes, labeled "id (count)" when the lexeme differs
      epsilon       : plain text
    """
    graph = graphviz.Digraph("parse_tree")
    graph.attr("graph", ordering="out")     # keep children in left-to-right order
    graph.attr("node", fontname="Helvetica")

    counter = [0]   # a list so the inner function can change it

    def add_node(node):
        counter[0] += 1
        node_id = f"n{counter[0]}"

        if grammar.is_non_terminal(node.symbol):
            graph.node(node_id, node.label(), shape="ellipse")
        elif node.symbol in grammar.terminals:
            graph.node(node_id, node.label(), shape="box")
        else:
            graph.node(node_id, node.label(), shape="plaintext")   # epsilon

        for child in node.children:
            child_id = add_node(child)
            graph.edge(node_id, child_id)
        return node_id

    add_node(root)
    return graph


if __name__ == "__main__":
    # Usage: python visualize.py <grammar-file> [--method slr|clr|lalr] [--out NAME]
    # Draws the automaton the chosen table is built from; states with conflicts are red.
    #   slr  -> LR(0) automaton            output/<name>_slr_automaton.png
    #   clr  -> LR(1) automaton            output/<name>_clr_automaton.png
    #   lalr -> merged LALR(1) automaton   output/<name>_lalr_automaton.png
    sys.stdout.reconfigure(encoding="utf-8")
    from grammar import load_grammar
    from tables import build_parsing_table, pop_option, METHOD_NAMES

    args = sys.argv[1:]
    out = pop_option(args, "--out")
    method = pop_option(args, "--method", "slr")
    if not args or method not in METHOD_NAMES:
        print("Usage: python visualize.py <grammar-file> [--method slr|clr|lalr] [--out NAME]")
        sys.exit(1)

    g = load_grammar(args[0])
    table = build_parsing_table(g, method)
    kind = {"slr": "LR(0) automaton", "clr": "LR(1) automaton",
            "lalr": "LALR(1) automaton (merged LR(1) states)"}[method]

    graph = automaton_graph(g, table.states, table.transitions, table.conflict_states(),
                            title=f"{kind} for {args[0]}  (red = {table.name} conflict)",
                            merged_from=table.merged_from)
    save_graph(graph, output_base_name(args[0], out) + f"_{method}_automaton")
