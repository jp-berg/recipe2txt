SRC_DIR = recipe2txt
UTILS_DIR = $(SRC_DIR)/utils

SRC = $(wildcard $(SRC_DIR)/*.py)
UTILS = $(wildcard $(UTILS_DIR)/*.py)
ALL_PY = $(SRC) $(UTILS) re2txt.py

DEBUG_OUT = tests/testfiles/recipe_test.txt tests/testfiles/recipe_test.md
JUNK = $(DEBUG_OUT)


testrun: clean
	 python3 re2txt.py -v4 -d -md -f ./test/testfiles/urls.txt
	 
test: testfiles
	python3 -m unittest

testfiles:
	python3 -m test.testfiles.html2recipe.testfile_generator

clean:
		rm  $(JUNK) || true

.PHONY: test testfiles
