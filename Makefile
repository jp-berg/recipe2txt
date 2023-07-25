VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(PYTHON) -m pip
TESTFILES = ./test/testfiles
TESTFILES_PERMANENT_PY = $(filter-out %__init__.py, $(wildcard $(TESTFILES)/permanent/*.py)) # get all .py-files, except __init__.py
TESTFILE_PERMANENT_TMP = $(patsubst ./%.py, -m %, $(TESTFILES_PERMANENT_PY)) # Remove leading './' and trailing '.py', add '-m' in front
TESTFILE_PERMANENT_MODULES = $(subst /,., $(TESTFILE_PERMANENT_TMP)) # replace '/' with '.'
TMP_TESTFILE_DIR = $(TESTFILES)/tmp_testfiles_re2txt
RE2TXT = -m recipe2txt.re2txt

testrun: testrun1 testrun2 testrun3

testrun1: $(PYTHON)
	$^ $(RE2TXT) -v info -d -md -f $(TESTFILES)/urls.txt -o $(TESTFILES)/recipe_test.md -con 10 -t 20

testrun2: $(PYTHON)
	$^ $(RE2TXT) -v info -d -f $(TESTFILES)/urls2.txt -o $(TESTFILES)/recipe_test2.txt -con 1 -t 20

testrun3: $(PYTHON)
	$^ $(RE2TXT) -v info -d -md -f $(TESTFILES)/urls3.txt $(TESTFILES)/urls4.txt $(TESTFILES)/urls5.txt -o $(TESTFILES)/recipe_test3.md -con 10 -t 20

$(PYTHON):
	python3 -m venv $(VENV);
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements_performance.txt

mypy: $(PYTHON)
	mypy $(RE2TXT) $(TESTFILE_PERMANENT_MODULES) -m test.test_helpers --python-executable $^ --strict

test: $(PYTHON)
	$(PYTHON) -m unittest
	rm -rf $(TMP_TESTFILE_DIR) || True

uninstall:
	rm -rf $(VENV)

.PHONY: test testfiles test1 test2 test3
