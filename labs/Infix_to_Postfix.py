# p3_infix_to_postfix.py
import re

PREC = {'+': 1, '-': 1, '*': 2, '/': 2, '%': 2, '^': 3}
RIGHT_ASSOC = {'^'}

def infix_to_postfix(expr, trace=True):
    tokens = re.findall(r'\d+\.?\d*|[A-Za-z_]\w*|[-+*/%^()]', expr)
    out, stack = [], []

    if trace:
        print(f"{'Token':<8}{'Stack':<20}{'Output'}")
        print("-" * 50)

    for t in tokens:
        if t == '(':
            stack.append(t)
        elif t == ')':
            while stack and stack[-1] != '(':
                out.append(stack.pop())
            if not stack:
                raise ValueError("Mismatched parentheses")
            stack.pop()                       # '(' remove
        elif t in PREC:
            while (stack and stack[-1] != '(' and
                   (PREC[stack[-1]] > PREC[t] or
                    (PREC[stack[-1]] == PREC[t] and t not in RIGHT_ASSOC))):
                out.append(stack.pop())
            stack.append(t)
        else:                                  # operand
            out.append(t)

        if trace:
            print(f"{t:<8}{' '.join(stack):<20}{' '.join(out)}")

    while stack:
        if stack[-1] == '(':
            raise ValueError("Mismatched parentheses")
        out.append(stack.pop())
        if trace:
            print(f"{'pop':<8}{' '.join(stack):<20}{' '.join(out)}")

    return ' '.join(out)

if __name__ == "__main__":
    e = input("Enter infix expression: ")
    print("\nPostfix:", infix_to_postfix(e))