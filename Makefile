VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(PYTHON) -m pip
TESTFILES = ./test/testfiles

testrun: testrun1 testrun2 testrun3

testrun1: $(PYTHON)
	$^ re2txt.py -v info -d -md -f $(TESTFILES)/urls.txt -o $(TESTFILES)/recipe_test.md -con 10 -t 20

testrun2: $(PYTHON)
	$^ re2txt.py -v info -d -f $(TESTFILES)/urls2.txt -o $(TESTFILES)/recipe_test2.txt -con 1 -t 20

testrun3: $(PYTHON)
	$^ re2txt.py -v info -d -md -f $(TESTFILES)/urls3.txt $(TESTFILES)/urls4.txt $(TESTFILES)/urls5.txt -o $(TESTFILES)/recipe_test3.md -con 10 -t 20

$(PYTHON):
	python3 -m venv $(VENV);
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements_performance.txt

mypy: $(PYTHON)
	mypy -m re2txt -m $(TESTFILE_GEN) -m test.test_helpers --python-executable $^ --strict

test: $(PYTHON)
	$(PYTHON) -m unittest

uninstall:
	rm -rf $(VENV)

.PHONY: test testfiles test1 test2 test3
