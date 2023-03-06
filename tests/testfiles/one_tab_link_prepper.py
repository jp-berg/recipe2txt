from os import linesep

def convert(file: str):
    with open(file, 'r') as file:
         lines = file.readlines()
         lines = [l[:l.find(" | ")] + linesep for l in lines]
         
    with open(file, 'w') as file:
         [file.write(l) for l in lines]

if __name__ == '__main__':
    convert("urls.txt")
