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


def state_label(grammar, i, items, is_accept, has_conflict):
    """
    Build the HTML-like label of one state: a small table with
      row 1     : the state name (I0, I1, ...)
      next rows : kernel items
      a line    : <HR/>
      next rows : closure items, in grey
    """
    title = f"I{i}"
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
    closure_items = []
    for item in items:
        if item.is_kernel(grammar):
            kernel.append(item)
        else:
            closure_items.append(item)

    rows = []
    rows.append(f'<TR><TD><B>{html_text(title)}</B></TD></TR>')
    for item in kernel:
        rows.append(f'<TR><TD ALIGN="LEFT">{html_text(str(item))}</TD></TR>')
    if closure_items:
        rows.append("<HR/>")
        for item in closure_items:
            rows.append(f'<TR><TD ALIGN="LEFT"><FONT COLOR="#666666">'
                        f'{html_text(str(item))}</FONT></TD></TR>')

    table = (f'<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3" '
             f'COLOR="{border_color}" BGCOLOR="{background}">'
             + "".join(rows) + "</TABLE>")
    # The extra < > around the table tell Graphviz this is an HTML-like label.
    return "<" + table + ">"


def automaton_graph(grammar, states, transitions, conflict_states=None, title=None):
    """
    Build the Graphviz graph of the LR(0) automaton.
    conflict_states: set of state numbers to draw in red (from the parsing table).
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
        label = state_label(grammar, i, states[i],
                            is_accept=(i == accept_state),
                            has_conflict=(i in conflict_states))
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
    # Usage: python visualize.py <grammar-file> [--out NAME]
    # Draws the LR(0) automaton; states with SLR(1) conflicts are red.
    sys.stdout.reconfigure(encoding="utf-8")
    from grammar import load_grammar
    from lr0 import canonical_collection
    from tables import build_slr_table, find_conflicts

    args = sys.argv[1:]
    out = None
    if "--out" in args:
        k = args.index("--out")
        out = args[k + 1]
        del args[k:k + 2]
    if not args:
        print("Usage: python visualize.py <grammar-file> [--out NAME]")
        sys.exit(1)

    g = load_grammar(args[0])
    C, trans = canonical_collection(g)
    action, goto_table = build_slr_table(g, C, trans)
    conflict_states = set()
    for c in find_conflicts(action):
        conflict_states.add(c["state"])

    graph = automaton_graph(g, C, trans, conflict_states,
                            title=f"LR(0) automaton for {args[0]}  (red = SLR(1) conflict)")
    save_graph(graph, output_base_name(args[0], out) + "_automaton")
