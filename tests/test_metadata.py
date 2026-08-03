# Copyright (C) 2022 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import builtins
from importlib.util import module_from_spec, spec_from_file_location
import types
from unittest.mock import patch

import ansys.platform.instancemanagement as pypim
from ansys.platform.instancemanagement import __version__


def test_pkg_version():
    assert __version__ == "1.2.dev0"


def test_importlib_metadata_fallback_branch():
    module_path = pypim.__file__
    spec = spec_from_file_location("_pypim_test_fallback", module_path)
    module = module_from_spec(spec)
    fake_importlib_metadata = types.SimpleNamespace(version=lambda _: "1.2.dev0")
    original_import = builtins.__import__

    def custom_import(name, globals_=None, locals_=None, fromlist=(), level=0):
        if name == "importlib.metadata":
            raise ModuleNotFoundError("forced missing importlib.metadata")
        return original_import(name, globals_, locals_, fromlist, level)

    with (
        patch("builtins.__import__", side_effect=custom_import),
        patch.dict("sys.modules", {"importlib_metadata": fake_importlib_metadata}),
    ):
        spec.loader.exec_module(module)

    assert module.__version__ == "1.2.dev0"
