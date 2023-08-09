VENV = .venv
PYTHON_VENV = $(VENV)/bin/python
PIP = $(PYTHON_VENV) -m pip
RE2TXT = -m recipe2txt.re2txt

PY_DEPS = pyproject-build mypy twine  # installable via pip
EXT_DEPS = python3 pipx rm find      # not installable via pip

PACKAGE_VERSION = $(shell python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
PACKAGE_WHL = dist/recipe2txt-$(PACKAGE_VERSION)-py3-none-any.whl
PACKAGE_TAR = dist/recipe2txt-$(PACKAGE_VERSION).tar.gz
PACKAGE = $(PACKAGE_WHL) $(PACKAGE_TAR)

TESTFILES = ./test/testfiles
TMP_TESTFILE_DIR = $(TESTFILES)/tmp_testfiles_re2txt
TEST4RE2TXT = -m test.test4recipe2txt

TESTFILES_PERMANENT_PY = $(filter-out %__init__.py, $(wildcard $(TESTFILES)/permanent/*.py))  # get all .py-files, except __init__.py
TESTFILE_PERMANENT_TMP = $(patsubst ./%.py, -m %, $(TESTFILES_PERMANENT_PY))                  # Remove leading './' and trailing '.py', add '-m' in front
TESTFILE_PERMANENT_MODULES = $(subst /,., $(TESTFILE_PERMANENT_TMP))                          # replace '/' with '.'

PYCACHE = $(shell find -type d -name '__pycache__')
ARTIFACTS = $(TMP_TESTFILE_DIR) dist $(TESTFILES)/debug-dirs test/reports_test4recipe2txt recipe2txt.egg-info $(PYCACHE)

get_path = $(shell command -v $(1) 2> /dev/null)
get_bin = $(or $(call get_path,$(1)), $(error '$(1)' not found in PATH))
get_py = $(or $(call get_path,$(1)), \
              $(and $(shell pipx install $(1)), $(call get_path,$(1))), \
              $(error Could not install '$(1)'))

install: $(PACKAGE_WHL) pipx #See EXT_DEPS
	pipx install $^

release: | $(PACKAGE) twine #See PY_DEPS
	twine upload $(PACKAGE)

test-all: | $(PYTHON_VENV)
	$^ $(TEST4RE2TXT) --format md -i file --long-timeout --delete-database --number-of-urls -1

test-txt: | $(PYTHON_VENV)
	$^ $(TEST4RE2TXT) --format txt --delete-database

test-md: | $(PYTHON_VENV)
	$^ $(TEST4RE2TXT) --format md --delete-database

test-synchronous: | $(PYTHON_VENV)
	$^ $(TEST4RE2TXT) --delete-database --connections 1

$(PY_DEPS): | $(PYTHON_VENV) # Check if the target is installed, if not try to install it via pip, if that does not work exit
	@ . .venv/bin/activate && command -v $@ 1> /dev/null || $(PIP) install $@ || (echo "Program '"$@"' not found and cannot be installed via '" $(PIP) "'" && exit 1)

$(EXT_DEPS):
	@ command -v $@ 1> /dev/null || (echo "Program '"$@"' not found" && exit 1)

$(VENV): | python3
	python3 -m venv $@

$(PYTHON_VENV): | $(VENV) python3 #See EXT_DEPS
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements_performance.txt

check:  | $(PYTHON_VENV) mypy #See PY_DEPS
	mypy $(RE2TXT) $(TEST4RE2TXT) $(TESTFILE_PERMANENT_MODULES) -m test.test_helpers --python-executable $(PYTHON_VENV) --strict

unittest: | check rm #See EXT_DEPS
	$(PYTHON_VENV) -m unittest
	rm -rf $(TMP_TESTFILE_DIR) || True

$(PACKAGE): | unittest pyproject-build #See PY_DEPS
	pyproject-build

test: unittest test-all

clean: | rm find
	rm -rf $(ARTIFACTS) || True

uninstall: clean
	rm -rf $(VENV)

.PHONY: test
