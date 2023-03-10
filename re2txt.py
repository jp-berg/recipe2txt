import recipe2txt.main as main
from sys import argv

if __name__ == '__main__':
    main.main(argv[1:], debug=True, args_are_files=True, verbosity=4)

