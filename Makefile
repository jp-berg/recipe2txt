SRC_DIR = recipe2txt
UTILS_DIR = $(SRC_DIR)/utils

SRC = $(wildcard $(SRC_DIR)/*.py)
UTILS = $(wildcard $(UTILS_DIR)/*.py)
ALL_PY = $(SRC) $(UTILS) re2txt.py

DEBUG_OUT = tests/testfiles/recipe_test.txt
JUNK = $(DEBUG_OUT)


testrun: clean
	 python3 re2txt.py -v4 -d -f ./tests/testfiles/urls.txt

clean:
		rm  $(JUNK) || true

