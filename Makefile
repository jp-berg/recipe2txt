VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(PYTHON) -m pip
RE2TXT = -m recipe2txt.re2txt

TESTFILES = ./test/testfiles
TMP_TESTFILE_DIR = $(TESTFILES)/tmp_testfiles_re2txt
TEST4RE2TXT = -m test.test4recipe2txt

TESTFILES_PERMANENT_PY = $(filter-out %__init__.py, $(wildcard $(TESTFILES)/permanent/*.py)) 	# get all .py-files, except __init__.py
TESTFILE_PERMANENT_TMP = $(patsubst ./%.py, -m %, $(TESTFILES_PERMANENT_PY)) 			# Remove leading './' and trailing '.py', add '-m' in front
TESTFILE_PERMANENT_MODULES = $(subst /,., $(TESTFILE_PERMANENT_TMP)) 				# replace '/' with '.'



test-all: $(PYTHON)
	$^ $(TEST4RE2TXT) --format md -i file --long-timeout --delete-database

test-txt: $(PYTHON)
	$^ $(TEST4RE2TXT) --format txt --delete-database

test-md: $(PYTHON)
	$^ $(TEST4RE2TXT) --format md --delete-database

test-synchronous: $(PYTHON)
	$^ $(TEST4RE2TXT) --delete-database --connections 1

$(PYTHON):
	python3 -m venv $(VENV);
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements_performance.txt

mypy: $(PYTHON)
	mypy $(RE2TXT) $(TEST4RE2TXT) $(TESTFILE_PERMANENT_MODULES) -m test.test_helpers --python-executable $^ --strict

unittest: mypy
	$(PYTHON) -m unittest
	rm -rf $(TMP_TESTFILE_DIR) || True

uninstall:
test: unittest test-all
	rm -rf $(VENV)

.PHONY: test
