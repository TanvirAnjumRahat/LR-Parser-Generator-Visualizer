# p1_syntax_tree.py
import re

TOKEN_RE = re.compile(r'\s*(?:(\d+\.?\d*)|([A-Za-z_]\w*)|(.))')

def tokenize(s):
    toks = []
    for num, idn, op in TOKEN_RE.findall(s):
        if num:   toks.append(('num', num))
        elif idn: toks.append(('id', idn))
        elif op:  toks.append((op, op))
    toks.append(('$', '$'))
    return toks

class Node:
    def __init__(self, label, children=None):
        self.label = label
        self.children = children or []

def show(n, prefix="", last=True, root=True):
    if root:
        print(n.label)
    else:
        print(prefix + ("└── " if last else "├── ") + n.label)
        prefix += "    " if last else "│   "
    for i, c in enumerate(n.children):
        show(c, prefix, i == len(n.children) - 1, False)

class Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i][0]

    def eat(self, kind):
        if self.peek() != kind:
            raise SyntaxError(f"Expected '{kind}' but found '{self.peek()}'")
        tok = self.t[self.i]
        self.i += 1
        return Node(tok[1])

    def E(self):
        return Node('E', [self.T(), self.Ep()])

    def Ep(self):
        if self.peek() in ('+', '-'):
            op = self.eat(self.peek())
            return Node("E'", [op, self.T(), self.Ep()])
        return Node("E'", [Node('ε')])

    def T(self):
        return Node('T', [self.F(), self.Tp()])

    def Tp(self):
        if self.peek() in ('*', '/'):
            op = self.eat(self.peek())
            return Node("T'", [op, self.F(), self.Tp()])
        return Node("T'", [Node('ε')])

    def F(self):
        k = self.peek()
        if k == '(':
            l = self.eat('(')
            e = self.E()
            r = self.eat(')')
            return Node('F', [l, e, r])
        if k in ('id', 'num'):
            return Node('F', [self.eat(k)])
        raise SyntaxError(f"Unexpected token '{k}'")

if __name__ == "__main__":
    expr = input("Enter expression: ")
    p = Parser(tokenize(expr))
    tree = p.E()
    if p.peek() != '$':
        raise SyntaxError("Extra input after expression")
    print("\nSyntax (Parse) Tree:\n")
    show(tree)