# p4_keyword_identifier.py
import re

KEYWORDS = {
    'auto', 'break', 'case', 'char', 'const', 'continue', 'default', 'do',
    'double', 'else', 'enum', 'extern', 'float', 'for', 'goto', 'if', 'int',
    'long', 'register', 'return', 'short', 'signed', 'sizeof', 'static',
    'struct', 'switch', 'typedef', 'union', 'unsigned', 'void', 'volatile',
    'while'
}

TOKEN_SPEC = [
    ('WORD',   r'[A-Za-z_]\w*'),
    ('NUMBER', r'\d+\.?\d*'),
    ('OP',     r'==|!=|<=|>=|\+\+|--|&&|\|\||[-+*/%=<>!&|^~]'),
    ('PUNCT',  r'[(){}\[\];,.:#]'),
    ('SKIP',   r'\s+'),
    ('OTHER',  r'.'),
]
MASTER = re.compile('|'.join(f'(?P<{n}>{p})' for n, p in TOKEN_SPEC))

def classify(code):
    result = []
    for m in MASTER.finditer(code):
        kind, text = m.lastgroup, m.group()
        if kind == 'SKIP':
            continue
        if kind == 'WORD':
            kind = 'KEYWORD' if text in KEYWORDS else 'IDENTIFIER'
        result.append((text, kind))
    return result

if __name__ == "__main__":
    print("Enter code (empty line to finish):")
    lines = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line)
    code = '\n'.join(lines)

    print(f"\n{'Lexeme':<15}{'Token Type'}")
    print("-" * 30)
    for text, kind in classify(code):
        print(f"{text:<15}{kind}")