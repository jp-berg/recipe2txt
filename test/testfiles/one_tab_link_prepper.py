from os import linesep


def convert(file: str):
    with open(file, 'r') as f:
        lines = f.readlines()
        lines = [line[:line.find(" | ")] + linesep for line in lines]
         
    with open(file, 'w') as ff:
         [f.write(line) for line in lines]


if __name__ == '__main__':
    convert("urls.txt")
