import recipe2txt.main
from sys import argv

if __name__ == '__main__':
    recipe2txt.main.main(argv[1:], debug=True, args_are_files=True, verbosity=4)

