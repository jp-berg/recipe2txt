VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(PYTHON) -m pip

testrun: testrun1 testrun2 testrun3

testrun1: $(PYTHON)
	$^ re2txt.py -v info -d -md -f ./test/testfiles/urls.txt -o ./test/testfiles/recipe_test.md -con 10 -t 20

testrun2: $(PYTHON)
	$^ re2txt.py -v info -d -f ./test/testfiles/urls2.txt -o ./test/testfiles/recipe_test2.txt -con 1 -t 20

testrun3: $(PYTHON)
	$^ re2txt.py -v info -d -md -f ./test/testfiles/urls3.txt ./test/testfiles/urls4.txt ./test/testfiles/urls5.txt -o ./test/testfiles/recipe_test3.md -con 10 -t 20

$(PYTHON):
	python3 -m venv $(VENV);
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements_performance.txt

mypy: $(PYTHON)
	mypy -m re2txt -m test.testfiles.permanent.testfile_generator --python-executable $^ --strict

test: $(PYTHON) testfiles
	$(PYTHON) -m unittest

testfiles: $(PYTHON)
	$^ -m test.testfiles.html2recipe.testfile_generator;

uninstall:
	rm -rf $(VENV)

.PHONY: test testfiles test1 test2 test3
