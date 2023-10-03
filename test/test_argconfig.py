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
import textwrap
import unittest
from typing import Any

import recipe2txt.utils.ArgConfig as argconfig
from recipe2txt.utils.misc import ensure_existence_dir
from test.test_helpers import assertEval, test_project_tmpdir, delete_tmpdirs


class TestFunctions(unittest.TestCase):

    def test_short_flag(self):
        params = [("verbose", "-v"),
                  ("file", "-f"),
                  ("set-location", "-sl"),
                  ("no-overwrite-files", "-nof")]

        assertEval(self, argconfig.short_flag, params)

    def test_obj2toml(self):
        params = [(True, "true"),
                  ("test", "'test'"),
                  ([1, 2, 3], "[1, 2, 3]"),
                  (["one", "two", "three"], "['one', 'two', 'three']"),
                  ({"four": True, "five": False, "six": True},
                   "{'four': true, 'five': false, 'six': true}")]

        assertEval(self, argconfig.obj2toml, params)


valid_string_1 = textwrap.dedent(
    """


    # This is a helptext

    #test = 'yes'
     """)
params_1 = {"name": "test", "help_str": "This is a helptext", "default": "yes"}

valid_string_2 = textwrap.dedent(
    """
    
    
    #flag = 3
    """
)
params_2 = {"name": "flag", "help_str": "", "default": 3}

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
params_3 = {"name": "option", "help_str": help_txt_3, "default": True}

params = [(params_1, valid_string_1),
          (params_2, valid_string_2),
          (params_3, valid_string_3)]


class TestInit(unittest.TestCase):

    def assertValidInit(self, option: argconfig.BasicOption, validation: dict[str, Any]):
        v_name = validation["name"]
        self.assertEqual(option.name, v_name)
        self.assertEqual(option.names, [f"--{v_name}", f"-{v_name[0]}"])

        self.assertEqual(option.arguments[argconfig.ArgKey.help], validation["help_str"])
        self.assertEqual(option.arguments[argconfig.ArgKey.default], validation["default"])


class TestBasicOption(TestInit):

    def test_init(self):
        p = {"name": "test", "help_str": "text", "default": "yes"}
        b = argconfig.BasicOption(**p)
        self.assertValidInit(b, p)

        p_short = p | {"short": "tst"}
        b = argconfig.BasicOption(**p_short)
        self.assertEqual(b.names, ["--test", "-tst"])

        invalid_params = [{"name": "--test"},
                          {"short": "-t"},
                          {"short": "testoption"}]

        for idx, invalid in enumerate(invalid_params):
            with self.subTest(i=idx, parameter=invalid):
                p_invalid = p | invalid
                with self.assertRaises(ValueError):
                    b = argconfig.BasicOption(**p_invalid)

        for idx, (init_params, _) in enumerate(params):
            with self.subTest(i=idx, parameter=init_params):
                b = argconfig.BasicOption(**init_params)
                self.assertValidInit(b, init_params)

    def test_to_toml_str(self):
        for idx, (init_params, valid_string) in enumerate(params):
            with self.subTest(i=idx, parameter=init_params):
                b = argconfig.BasicOption(**init_params)
                self.assertEqual(b.to_toml_str(), valid_string)

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

        tomldict = {init_param["name"]: f"NEW DEFAULT VALUE {idx}"
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
co_params_1 = {"name": "speed", "help_str": "Adjust the speed", "default": "slow",
               "choices": ["slow", "normal", "fast"]}

co_valid_string_2 = textwrap.dedent(
    """
    
    
    # Set the coin-denomination
    
    #cents = 50 # Possible values: 1 | 2 | 5 | 10 | 20 | 50
    
    """
)
co_params_2 = {"name": "cents", "help_str": "Set the coin-denomination", "default": 50,
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

    def test_to_toml_str(self):
        for idx, (init_params, valid_string) in enumerate(co_params):
            with self.subTest(i=idx, parameter=init_params):
                c = argconfig.ChoiceOption(**init_params)
                self.assertEqual(c.to_toml_str(), valid_string)

    def test_toml_valid(self):
        for idx, (init_params, valid_string) in enumerate(co_params):
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
t_params_1 = {"name": "delay", "help_str": "Sets the delay between application call and execution (in seconds)",
              "default": 0.5, "t": float}


t_valid_string_2 = textwrap.dedent(
    """
    
    
    # How many times should the program retry to fetch the resource on failure
    #retries = 3
    """
)
t_params_2 = {"name": "retries", "help_str": "How many times should the program retry to fetch the resource on failure",
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











