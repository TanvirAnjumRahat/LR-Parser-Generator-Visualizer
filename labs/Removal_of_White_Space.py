# p5_remove_whitespace.py
import re

def strip_comments(code):
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.S)   # /* ... */
    code = re.sub(r'//[^\n]*', '', code)                # // ...
    return code

def compress_whitespace(code):
    """Extra space/tab/newline কমিয়ে single space রাখে"""
    code = strip_comments(code)
    lines = [re.sub(r'[ \t]+', ' ', l).strip() for l in code.splitlines()]
    return ' '.join(l for l in lines if l)

def remove_all_whitespace(code):
    """সব whitespace পুরোপুরি মুছে ফেলে"""
    return re.sub(r'\s+', '', strip_comments(code))

if __name__ == "__main__":
    print("Enter code (empty line to finish):")
    lines = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line)
    code = '\n'.join(lines)

    print("\nOriginal length          :", len(code))
    print("After compress           :", compress_whitespace(code))
    print("After removing all space :", remove_all_whitespace(code))