# p2_ast.py
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
    def __init__(self, val, left=None, right=None):
        self.val, self.left, self.right = val, left, right

def show(n, prefix="", last=True, root=True):
    if root:
        print(n.val)
    else:
        print(prefix + ("└── " if last else "├── ") + n.val)
        prefix += "    " if last else "│   "
    kids = [c for c in (n.left, n.right) if c]
    for i, c in enumerate(kids):
        show(c, prefix, i == len(kids) - 1, False)

def to_prefix(n):
    if not n.left and not n.right:
        return n.val
    return f"({n.val} {to_prefix(n.left)} {to_prefix(n.right)})"

class Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i][0]

    def next(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def expr(self):                       # + -
        left = self.term()
        while self.peek() in ('+', '-'):
            op = self.next()[1]
            left = Node(op, left, self.term())
        return left

    def term(self):                       # * /
        left = self.factor()
        while self.peek() in ('*', '/'):
            op = self.next()[1]
            left = Node(op, left, self.factor())
        return left

    def factor(self):
        k = self.peek()
        if k == '(':
            self.next()
            n = self.expr()
            if self.peek() != ')':
                raise SyntaxError("Missing ')'")
            self.next()
            return n
        if k in ('id', 'num'):
            return Node(self.next()[1])
        raise SyntaxError(f"Unexpected token '{k}'")

if __name__ == "__main__":
    expr = input("Enter expression: ")
    p = Parser(tokenize(expr))
    ast = p.expr()
    if p.peek() != '$':
        raise SyntaxError("Extra input after expression")
    print("\nAbstract Syntax Tree:\n")
    show(ast)
    print("\nPrefix form:", to_prefix(ast))