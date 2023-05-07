VENV = .venv
ACTIVATE = . $(VENV)/bin/activate
# delete this file to reinstall the requirements to the venv:
REQ = .req


SRC_DIR = recipe2txt
UTILS_DIR = $(SRC_DIR)/utils

SRC = $(wildcard $(SRC_DIR)/*.py)
UTILS = $(wildcard $(UTILS_DIR)/*.py)
ALL_PY = $(SRC) $(UTILS) re2txt.py

DEBUG_OUT = tests/testfiles/recipe_test.txt tests/testfiles/recipe_test.md
JUNK = $(DEBUG_OUT)


testrun: clean
	 python3 re2txt.py -v4 -d -md -f ./test/testfiles/urls.txt
	 
$(REQ): $(VENV)
	. $(ACTIVATE); pip install -r requirements.txt; touch $@

$(VENV):
	python3 -m venv $@

test: testfiles $(REQ)
	$(ACTIVATE); python3 -m unittest

testfiles: $(REQ)
	$(ACTIVATE); python3 -m test.testfiles.html2recipe.testfile_generator

clean:
		rm  $(JUNK) || true

.PHONY: test testfiles
