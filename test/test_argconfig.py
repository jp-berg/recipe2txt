# Copyright (C) 2023 Jan Philipp Berg <git.7ksst@aleeas.com>
#
# This file is part of recipe2txt.
#
# recipe2txt is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# recipe2txt is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with recipe2txt.
# If not, see <https://www.gnu.org/licenses/>.
import itertools
import os
import random
import shutil
import textwrap
import unittest
from typing import Any

import recipe2txt.utils.ArgConfig as argconfig
from recipe2txt.argparse import config_args
from recipe2txt.fetcher import Fetcher
from recipe2txt.file_setup import CONFIG_NAME, debug_dirs, DEBUG_DIRECTORY_BASE, get_default_output
from recipe2txt.utils.misc import ensure_existence_dir, ensure_accessible_file
from test.test_helpers import assertEval, test_project_tmpdir, delete_tmpdirs


class TestFunctions(unittest.TestCase):

    def test_short_flag(self):
        params = [("--verbose", "-v"),
                  ("--file", "-f"),
                  ("--set-location", "-sl"),
                  ("--no-overwrite-files", "-nof")]

        assertEval(self, argconfig.short_flag, params)
        with self.assertRaises(ValueError):
            argconfig.short_flag("file-types")

    def test_obj2toml(self):
        params = [(True, "true"),
                  ("test", "'test'"),
                  ([1, 2, 3], "[1, 2, 3]"),
                  (["one", "two", "three"], "['one', 'two', 'three']"),
                  ({"four": True, "five": False, "six": True},
                   "{'four': true, 'five': false, 'six': true}"),
                  ([], "[]"),
                  ({}, "{}")]

        assertEval(self, argconfig.obj2toml, params)


valid_string_1 = textwrap.dedent(
    """


    # This is a helptext

    #test = 'yes'
     """)
params_1 = {"option_name": "--test", "help_str": "This is a helptext", "default": "yes"}

valid_string_2 = textwrap.dedent(
    """
    
    
    #flag = 3
    """
)
params_2 = {"option_name": "--flag", "help_str": "", "default": 3}

valid_string_3 = textwrap.dedent(
    """
    
    
    # This is a multiline help-text, providing far more information. But in
    # contrast to the other examples, this has to be wrapped. This makes the
    # information more easily digestible.
    
    #option = true
    """
)
help_txt_3 = "This is a multiline help-text, providing far more information. But in contrast to the other examples," \
             " this has to be wrapped. This makes the information more easily digestible."
params_3 = {"option_name": "--option", "help_str": help_txt_3, "default": True}

params = [(params_1, valid_string_1),
          (params_2, valid_string_2),
          (params_3, valid_string_3)]


class TestInit(unittest.TestCase):

    def assertValidInit(self, option: argconfig.BasicOption, validation: dict[str, Any]):
        v_name = validation["option_name"]
        self.assertEqual(option.name, v_name[2:] if v_name.startswith("--") else v_name)
        if validation["option_name"].startswith("--"):
            self.assertEqual(option.option_names, [v_name, f"{v_name[1:3]}"])
        else:
            self.assertEqual(option.option_names, [v_name])

        self.assertEqual(option.arguments[argconfig.ArgKey.help], validation["help_str"])
        self.assertEqual(option.arguments[argconfig.ArgKey.default], validation["default"])


class TestBasicOption(TestInit):

    def test_init(self):
        p = {"option_name": "--test", "help_str": "text", "default": "yes"}
        b = argconfig.BasicOption(**p)
        self.assertValidInit(b, p)

        p_short = p | {"short": "-tst"}
        b = argconfig.BasicOption(**p_short)
        self.assertEqual(b.option_names, ["--test", "-tst"])

        invalid_params = [{"option_name": "test", "short": "-t"},
                          {"short": "t"},
                          {"short": "-testoption"}]

        for idx, invalid in enumerate(invalid_params):
            with self.subTest(i=idx, parameter=invalid):
                p_invalid = p | invalid
                with self.assertRaises(ValueError):
                    b = argconfig.BasicOption(**p_invalid)

        for idx, (init_params, _) in enumerate(params):
            with self.subTest(i=idx, parameter=init_params):
                b = argconfig.BasicOption(**init_params)
                self.assertValidInit(b, init_params)

    def test_to_toml(self):
        self.assertIsNotNone(ensure_existence_dir(test_project_tmpdir))
        testpath = test_project_tmpdir / "TESTFILE.toml"

        for idx, (init_params, valid_string) in enumerate(params):
            with self.subTest(i=idx, parameter=init_params):
                b = argconfig.BasicOption(**init_params)
                b.to_toml(testpath)

                test_txt = testpath.read_text()
                self.assertEqual(test_txt, valid_string)
                os.remove(testpath)

        delete_tmpdirs()

    def test_from_toml(self):

        tomldict = {init_param["option_name"][2:]: f"NEW DEFAULT VALUE {idx}"
                    for idx, (init_param, _) in enumerate(params)}

        for idx, (init_params, _) in enumerate(params):
            with self.subTest(i=idx, parameter=init_params):
                b = argconfig.BasicOption(**init_params)
                self.assertEqual(b.arguments["default"], init_params["default"])
                b.from_toml(tomldict)
                self.assertEqual(b.arguments["default"], f"NEW DEFAULT VALUE {idx}")

        emptystuff = ["", {}, []]
        random.shuffle(emptystuff)
        tomldict_invalid = {key: empty for key, empty in zip(tomldict.keys(), itertools.cycle(emptystuff))}

        for idx, (init_params, _) in enumerate(params):
            with self.subTest(i=idx, parameter=init_params):
                b = argconfig.BasicOption(**init_params)

                b.from_toml(tomldict_invalid)
                self.assertEqual(b.arguments["default"], init_params["default"])


co_valid_string_1 = textwrap.dedent(
    """
    
    
    # Adjust the speed
    
    #speed = 'slow' # Possible values: 'slow' | 'normal' | 'fast'
    
    """
)
co_params_1 = {"option_name": "--speed", "help_str": "Adjust the speed", "default": "slow",
               "choices": ["slow", "normal", "fast"]}

co_valid_string_2 = textwrap.dedent(
    """
    
    
    # Set the coin-denomination
    
    #cents = 50 # Possible values: 1 | 2 | 5 | 10 | 20 | 50
    
    """
)
co_params_2 = {"option_name": "--cents", "help_str": "Set the coin-denomination", "default": 50,
               "choices": [1, 2, 5, 10, 20, 50]}

co_params = [(co_params_1, co_valid_string_1),
             (co_params_2, co_valid_string_2)]


class TestInitOption(TestInit):

    def assertValidInit(self, option: argconfig.BasicOption, validation: dict[str, Any]):
        super().assertValidInit(option, validation)
        self.assertEqual(option.arguments[argconfig.ArgKey.choices], validation["choices"])


class TestChoiceOption(TestInitOption):

    def test_init(self):
        for idx, (init_params, valid_string) in enumerate(co_params):
            with self.subTest(i=idx, parameter=init_params):
                c = argconfig.ChoiceOption(**init_params)
                self.assertValidInit(c, init_params)
                with self.assertRaises(ValueError):
                    faulty_params = init_params | {"default": valid_string}
                    c = argconfig.ChoiceOption(**faulty_params)

    def test_toml_valid(self):
        for idx, (init_params, _) in enumerate(co_params):
            with self.subTest(i=idx, parameter=init_params):
                c = argconfig.ChoiceOption(**init_params)
                for choice in init_params["choices"]:
                    with self.subTest(choice):
                        self.assertTrue(c.toml_valid(choice))
                self.assertFalse(c.toml_valid("WRONG VALUE THAT DOES NOT MAKE SENSE"))


t_valid_string_1 = textwrap.dedent(
    """
    
    
    # Sets the delay between application call and execution (in seconds)
    
    #delay = 0.5
    """
)
t_params_1 = {"option_name": "delay", "help_str": "Sets the delay between application call and execution (in seconds)",
              "default": 0.5, "t": float}

t_valid_string_2 = textwrap.dedent(
    """
    
    
    # How many times should the program retry to fetch the resource on
    # failure
    
    #retries = 3
    """
)
t_params_2 = {"option_name": "--retries",
              "help_str": "How many times should the program retry to fetch the resource on failure",
              "default": 3, "t": int}

t_params = [(t_params_1, t_valid_string_1),
            (t_params_2, t_valid_string_2)]


class TestInitType(TestInit):
    def assertValidInit(self, option: argconfig.BasicOption, validation: dict[str, Any]):
        super().assertValidInit(option, validation)
        self.assertEqual(option.arguments[argconfig.ArgKey.type], validation["t"])


class TestTypeOption(TestInitType):

    def test_init(self):
        for idx, (init_params, _) in enumerate(t_params):
            with self.subTest(i=idx, parameter=init_params):
                t = argconfig.TypeOption(**init_params)
                self.assertValidInit(t, init_params)

                p_without_t = init_params | {"t": None}
                t = argconfig.TypeOption(**p_without_t)
                self.assertValidInit(t, init_params)

                with self.assertRaises(ValueError):
                    p_invalid = init_params | {"default": "Not a good value"}
                    t = argconfig.TypeOption(**p_invalid)


b_valid_string_1 = textwrap.dedent(
    """

        
    # Whether the inputs should be validated before processing
    
    #validate-input = true # Possible values: true | false
    """)
b_params_1 = {"option_name": "--validate-input", "help_str": "Whether the inputs should be validated before processing",
              "default": True, "short": "-v"}

b_valid_string_2 = textwrap.dedent(
    """
    
    
    # Toggles debug-mode
    
    #debug = false # Possible values: true | false
    """
)

b_params_2 = {"option_name": "debug", "help_str": "Toggles debug-mode", "default": False}

b_params = [(b_params_1, b_valid_string_1),
            (b_params_2, b_valid_string_2)]


class TestInitBool(TestInit):

    def assertValidInit(self, option: argconfig.BasicOption, validation: dict[str, Any]):
        super().assertValidInit(option, validation)
        self.assertEqual(option.arguments[argconfig.ArgKey.action], "store_true")


class BoolOption(TestInitBool):

    def test_init(self):
        for idx, (init_params, _) in enumerate(b_params):
            with self.subTest(i=idx, parameter=init_params):
                b = argconfig.BoolOption(**init_params)
                self.assertValidInit(b, init_params)


n_valid_string_1 = textwrap.dedent(
    """
    
    
    # List of the ignored directories
    
    #ignored-directories = []
    """
)
n_params_1 = {"option_name": "--ignored-directories", "help_str": "List of the ignored directories", "short": "-i"}

n_valid_string_2 = textwrap.dedent(
    """
    
    
    # Values used as test-inputs
    
    #testvalues = [37, 29, 54, 66, 19, 59, 32]
    """
)
n_params_2 = {"option_name": "testvalues", "help_str": "Values used as test-inputs",
              "default": [37, 29, 54, 66, 19, 59, 32]}

n_valid_string_3 = textwrap.dedent(
    """
    
    
    # Phrases that will be blocked
    
    #banned = ['duck you', 'heck', 'darn']
    """
)
n_params_3 = {"option_name": "--banned", "help_str": "Phrases that will be blocked",
              "default": ["duck you", "heck", "darn"]}

n_params = [(n_params_1, n_valid_string_1),
            (n_params_2, n_valid_string_2),
            (n_params_3, n_valid_string_3)]


class TestInitNArg(TestInit):

    def assertValidInit(self, option: argconfig.BasicOption, validation: dict[str, Any]):
        super().assertValidInit(option, validation)
        self.assertEqual(option.arguments[argconfig.ArgKey.nargs], validation.get("narg", "*"))


class NArgOption(TestInitNArg):

    def test_init(self):
        for idx, (init_params, _) in enumerate(n_params):
            with self.subTest(i=idx, parameter=init_params):
                n = argconfig.NArgOption(**init_params)
                if "default" not in init_params:
                    init_params |= {"default": []}
                self.assertValidInit(n, init_params)


all_options = [(argconfig.BasicOption(**params), valid_string) for params, valid_string in params]
all_options += [(argconfig.ChoiceOption(**params), valid_string) for params, valid_string in co_params]
all_options += [(argconfig.TypeOption(**params), valid_string) for params, valid_string in t_params]
all_options += [(argconfig.BoolOption(**params), valid_string) for params, valid_string in b_params]
all_options += [(argconfig.NArgOption(**params), valid_string) for params, valid_string in n_params]

standard_params = {'url': [], 'file': [], 'output': get_default_output(),
                   'verbosity': 'critical', 'connections': 4, 'cache': 'default', 'debug': False,
                   'timeout': Fetcher.timeout, 'markdown': False, 'user_agent': Fetcher.user_agent,
                   'erase_appdata': None}

app_valid_string_1 = textwrap.dedent(
    """
    #file = ['/home/user/files/file.txt']
    output = '/home/pc/recipes.txt'
    connections = 3
    cache = 'new'
    debug = true
    markdown = true
    
    """
)
app_params_1 = {'url': ['www.test.com'], 'output': '/home/pc/recipes.txt',
                'connections': 3, 'cache': 'new', 'debug': True,  'markdown': True}

app_valid_string_2 = textwrap.dedent(
    """
    timeout = 9.3
    
    #This comment should not matter
    user-agent = "popular-browser on popular-platform"
    markdown = false
    """
)

app_params_2 = {'url': ['www.test.com'], 'timeout': 9.3, "user_agent": "popular-browser on popular-platform"}

app_params = [(app_params_1, app_valid_string_1),
              (app_params_2, app_valid_string_2)]

app_wrong_values = ["url = 'www.url.com'", "file = '/path/to/file'",
                    "connections = 1.7", "cache = true", "debug = 'yes, please!'", "timeout = true",
                    "verbosity = 'crutical'"]


class TestArgConfig(unittest.TestCase):

    def test_to_toml_str(self):
        for idx, (option, valid_string) in enumerate(all_options):
            with self.subTest(i=idx):
                self.assertEqual(option.to_toml_str(), valid_string)

    def tearDown(self) -> None:
        shutil.rmtree(DEBUG_DIRECTORY_BASE, ignore_errors=True)

    def test_app_argconfig(self):
        for idx, (changed_params, valid_string) in enumerate(app_params):
            with self.subTest(i=idx, parameter=params):
                f = ensure_accessible_file(debug_dirs.config, CONFIG_NAME)
                f.write_text(valid_string)
                p = config_args(f)
                d_parsed = vars(p.parse_args(["www.test.com"]))
                d_valid = standard_params | changed_params

                if diff1 := d_parsed.keys() - d_valid.keys():
                    diff_vals = {key: d_parsed.get(key) for key in diff1}
                    self.fail(f"There are more values in the parsed data than in the validation data: {diff_vals}")

                if diff2 := d_valid.keys() - d_parsed.keys():
                    diff_vals = {key: d_valid.get(key) for key in diff2}
                    self.fail(f"There are more values in the validation data than in the parsed data: {diff_vals}")

                for key in d_valid.keys():
                    with self.subTest(key=key):
                        self.assertEqual(d_parsed.get(key), d_valid.get(key))

    def test_app_argconfig_failure(self):
        for idx, malformed_string in enumerate(app_wrong_values):
            with self.subTest(malformed_string=malformed_string):
                f = ensure_accessible_file(debug_dirs.config, CONFIG_NAME)
                f.write_text(malformed_string + os.linesep)
                p = config_args(f)
                d_parsed = vars(p.parse_args(["www.test.com"]))
                d_valid = standard_params | {"url": ["www.test.com"]}

                for key in d_valid.keys():
                    with self.subTest(key=key):
                        self.assertEqual(d_parsed.get(key), d_valid.get(key))





