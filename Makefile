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


testrun: clean testrun1 testrun2 testrun3

testrun1: $(REQ)
	$(ACTIVATE); python3 re2txt.py -v info -d -md -f ./test/testfiles/urls.txt -o ./test/testfiles/recipe_test.md -con 10 -t 20

testrun2: $(REQ)
	$(ACTIVATE); python3 re2txt.py -v info -d -f ./test/testfiles/urls2.txt -o ./test/testfiles/recipe_test2.txt -con 1 -t 20

testrun3: $(REQ)
	$(ACTIVATE); python3 re2txt.py -v info -d -md -f ./test/testfiles/urls3.txt ./test/testfiles/urls4.txt ./test/testfiles/urls5.txt -o ./test/testfiles/recipe_test3.md -con 10 -t 20

$(REQ): $(VENV)
	$(ACTIVATE); pip install -r requirements.txt && pip install -r requirements_performance.txt && touch $@

$(VENV):
	python3 -m venv $@

mypy: $(REQ)
	$(ACTIVATE); mypy -m re2txt --python-executable .venv/bin/python3 --strict

test: $(REQ)
	$(ACTIVATE); python3 -m unittest

testfiles: $(REQ)
	$(ACTIVATE); python3 -m test.testfiles.html2recipe.testfile_generator;

clean:
	rm  $(JUNK) || true
	
uninstall:
	rm -rf $(VENV) || rm $(REQ) 

.PHONY: test testfiles test1 test2 test3
