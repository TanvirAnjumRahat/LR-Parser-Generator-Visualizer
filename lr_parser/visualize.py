"""
visualize.py - Graphviz drawings.

Phase 3: the parse tree (based on render_parse_tree() in labs/4.2).
(The LR(0) automaton diagram will be added in Phase 4.)

The drawing is described in the DOT language and saved as  output/<name>.dot.
If the Graphviz program "dot" is installed, it is also rendered to
output/<name>.png. Without it you can still paste the .dot file into an
online viewer such as https://dreampuf.github.io/GraphvizOnline
"""

import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")


def render_parse_tree(grammar, root, name):
    """
    Draw the parse tree rooted at 'root'.
      non-terminals : ellipses
      terminals     : boxes
      epsilon       : plain text
    Returns the path of the PNG, or of the .dot file if no PNG could be made.
    """
    try:
        import graphviz
    except ImportError:
        print("Parse tree not drawn: the 'graphviz' package is missing (pip install graphviz).")
        return None

    dot = graphviz.Digraph(name, comment="Parse tree")
    dot.attr("graph", ordering="out")     # keep children in left-to-right order
    dot.attr("node", fontname="Helvetica")

    counter = [0]   # a list so the inner function can change it

    def add_node(node):
        counter[0] += 1
        node_id = f"n{counter[0]}"

        if grammar.is_non_terminal(node.symbol):
            dot.node(node_id, node.symbol, shape="ellipse")
        elif node.symbol in grammar.terminals:
            dot.node(node_id, node.symbol, shape="box")
        else:
            dot.node(node_id, node.symbol, shape="plaintext")   # epsilon

        for child in node.children:
            child_id = add_node(child)
            dot.edge(node_id, child_id)
        return node_id

    add_node(root)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base_path = os.path.join(OUTPUT_DIR, name)
    dot_path = dot.save(base_path + ".dot")

    try:
        png_path = dot.render(base_path, format="png", cleanup=True)
    except graphviz.ExecutableNotFound:
        print(f"Parse tree saved as DOT source: {dot_path}")
        print("To get a PNG, install Graphviz (e.g. 'winget install graphviz') and make sure")
        print("'dot' is on your PATH, or open the .dot file in an online Graphviz viewer.")
        return dot_path

    print(f"Parse tree drawn: {png_path}")
    return png_path
