import pathlib
import re
import sys

FORBIDDEN = ("enumerate", "zip", "map", "next", "open")
SNIPPETS = pathlib.Path(__file__).resolve().parent.parent / "snippets"


def scan(path):
    hits = []
    text = path.read_text()
    line_no = 0
    for line in text.splitlines():
        line_no = line_no + 1
        for name in FORBIDDEN:
            if re.search(r"(?<![\w.])" + name + r"\s*\(", line):
                hits.append((path.name, line_no, name, line.strip()))
    return hits


def main():
    all_hits = []
    for path in sorted(SNIPPETS.glob("*.py")):
        all_hits.extend(scan(path))
    for name, ln, builtin, line in all_hits:
        print(name + ":" + str(ln) + ": forbidden '" + builtin + "()' -> " + line)
    if all_hits:
        sys.exit(1)
    print("sandbox scan clean")


if __name__ == "__main__":
    main()
