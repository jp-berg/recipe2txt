VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(PYTHON) -m pip
RE2TXT = -m recipe2txt.re2txt

PACKAGE_VERSION = $(shell $(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
PACKAGE = dist/recipe2txt-$(PACKAGE_VERSION)-py3-none-any.whl

TESTFILES = ./test/testfiles
TMP_TESTFILE_DIR = $(TESTFILES)/tmp_testfiles_re2txt
TEST4RE2TXT = -m test.test4recipe2txt

TESTFILES_PERMANENT_PY = $(filter-out %__init__.py, $(wildcard $(TESTFILES)/permanent/*.py)) 	# get all .py-files, except __init__.py
TESTFILE_PERMANENT_TMP = $(patsubst ./%.py, -m %, $(TESTFILES_PERMANENT_PY)) 			# Remove leading './' and trailing '.py', add '-m' in front
TESTFILE_PERMANENT_MODULES = $(subst /,., $(TESTFILE_PERMANENT_TMP)) 				# replace '/' with '.'

PYCACHE = $(shell find -type d -name '__pycache__')
ARTIFACTS = $(TMP_TESTFILE_DIR) dist $(TESTFILES)/debug-dirs test/reports_test4recipe2txt recipe2txt.egg-info $(PYCACHE)

install: $(PACKAGE)
	pipx install $^

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

$(PACKAGE): unittest
	pyproject-build

test: unittest test-all

clean:
	rm -rf $(ARTIFACTS) || True

uninstall: clean
	rm -rf $(VENV)

.PHONY: test
