import recipe2txt.rezepte
from sys import argv

if __name__ == '__main__':
    recipe2txt.rezepte.main(argv[1:], debug=True, args_are_files=True, verbosity=4)

