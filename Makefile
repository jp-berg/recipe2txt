# Returns the path to the command $(1) or stays empty if there is no such command in PATH
get_path = $(shell command -v $(1) 2> /dev/null)

# Returns the path to the command $(1) or exists the Makefile with an error if there is no such command in PATH
get_bin = $(or $(call get_path,$(1)), $(error '$(1)' not found in PATH))

PYTHON3 = $(call get_bin,python3)
RM = $(call get_bin,rm)
FIND = $(call get_bin,find)
PIPX = $(call get_bin,pipx)


#-----------
REQUIREMENTS = -r requirements.txt -r requirements_performance.txt
VENV_NAME = .venv
# If VENV_NAME cannot be found,...
# ...report the creaction of the virtual enviroment,...
# ...then try to create said enviroment (exit if that is not possible),...
# ...then report the installation of the requirements,...
# ...then try to install the requirements (if there are any errors, remove the virtual enviroments and exit),...
# ...then return the virtual enviroment name,...
# ...exit if that is not possible.
VENV = $(or $(wildcard $(VENV_NAME)), \
            $(info Creating virtual enviroment '$(VENV_NAME)'...), \
            $(and $(shell $(PYTHON3) -m venv $(VENV_NAME) 1> /dev/null),$(error Could not create virtual enviroment)), \
            $(info Installing requirements...), \
            $(and $(shell $(VENV_NAME)/bin/python -m pip install $(REQUIREMENTS) -),$(shell $(RM) -rf $(VENV_NAME)),$(error Could not install requirements)), \
            $(wildcard $(VENV_NAME)), \
            $(error Something went wrong))


BIN = $(VENV)/bin
PYTHON_VENV = $(BIN)/python
PIP = $(BIN)/pip
RE2TXT = -m recipe2txt.re2txt

#-----------
# Returns the path to the entry point to the Python package $(1) globally or locally
# or installs the package of the same name via pip and returns the path to the resulting entry point
# or exits the Makefile with an error if pip fails to install
get_py = $(or $(call get_path,$(1)), \
              $(wildcard $(BIN)/$(1)), \
              $(and $(shell $(PIP) install $(1)), $(wildcard $(BIN)/$(1))), \
              $(error Could not install '$(1)'))

BUILD = $(call get_py,pyproject-build)
TWINE = $(call get_py,twine)
PYMENT = $(call get_py,pyment)

#-----------
PACKAGE_VERSION = $(shell $(PYTHON3) -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
PACKAGE_WHL = dist/recipe2txt-$(PACKAGE_VERSION)-py3-none-any.whl
PACKAGE_TAR = dist/recipe2txt-$(PACKAGE_VERSION).tar.gz
PACKAGE = $(PACKAGE_WHL) $(PACKAGE_TAR)
#-----------
TESTFILES = ./test/testfiles
TMP_TESTFILE_DIR = $(TESTFILES)/tmp_testfiles_re2txt
TEST4RE2TXT = -m test.test4recipe2txt

PYCACHE = $(shell $(FIND) -type d -name '__pycache__')
ARTIFACTS = $(TMP_TESTFILE_DIR) dist $(TESTFILES)/debug-dirs test/reports_test4recipe2txt recipe2txt.egg-info $(PYCACHE)


install: $(PACKAGE_WHL)
	$(PIPX) install $^

release: $(PACKAGE)
	$(TWINE) upload $(PACKAGE)

test-all:
	$(PYTHON_VENV) $(TEST4RE2TXT) --format md -i file --long-timeout --delete-database --number-of-urls -1

test-txt: $(PYTHON_VENV)
	$(PYTHON_VENV) $(TEST4RE2TXT) --format txt --delete-database

test-md: $(PYTHON_VENV)
	$(PYTHON_VENV) $(TEST4RE2TXT) --format md --delete-database

test-synchronous: $(PYTHON_VENV)
	$(PYTHON_VENV)^ $(TEST4RE2TXT) --delete-database --connections 1

unittest: check
	$(PYTHON_VENV) -m unittest
	$(RM) -rf $(TMP_TESTFILE_DIR) || True

$(PACKAGE): unittest
	$(BULD)

test: unittest test-all

clean:
	$(RM) -rf $(ARTIFACTS) || True

uninstall: clean
	$(RM) -rf $(VENV_NAME)
# Call to $(VENV) would create the enviroment if it does not exist, then destroy it

.PHONY: test dummy
