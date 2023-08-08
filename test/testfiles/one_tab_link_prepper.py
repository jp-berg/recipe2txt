from os import linesep, remove, path
from sys import stderr, argv

def convert(file: str) -> None:
    if not path.isfile(file):
        print(f"Not a file {file}", file=stderr)
        return
    with open(file, 'r') as f:
        lines = f.readlines()
        lines = [line[:line.find(" | ")] + linesep for line in lines]
         
    with open(file, 'w') as ff:
         for line in lines:
             ff.write(line)


if __name__ == '__main__':
    for arg in argv[1:]:
        convert(arg)
