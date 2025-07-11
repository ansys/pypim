# Copyright (C) 2022 - 2025 ANSYS, Inc. and/or its affiliates.
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

import os
from unittest.mock import patch

import pytest

import ansys.platform.instancemanagement as pypim


def test_not_configured():
    with pytest.raises(pypim.NotConfiguredError):
        pypim.Configuration.from_environment()


@pytest.mark.parametrize(
    "bad_configuration,message_content",
    [
        (r"""not even the right format""", "json"),
        (r"""{"version": 2, "pim": "future format"}""", "Unsupported version"),
        (
            r"""{"version": 1, "pim": {
                "headers": {"token": "007","identity": "james bond"},"tls": false}}""",
            "uri",
        ),
        (r"""{"version": 1, "pim": {"uri": "dns:127.0.0.1:5000","tls": false}}""", "headers"),
        (
            r"""{"version": 1, "pim": {"uri": "dns:127.0.0.1:5000",
            "headers": {"token": "007","identity": "james bond"}}}""",
            "tls",
        ),
        (
            r"""{"version": 1, "pim": {"uri": "dns:127.0.0.1:5000", "tls": true,
            "headers": {"token": "007","identity": "james bond"}}}""",
            "authorization header with a bearer token is required",
        ),
    ],
)
def test_bad_configuration(tmp_path, bad_configuration, message_content):
    config_path = tmp_path / "pim.json"
    with open(config_path, "w") as f:
        f.write(bad_configuration)

    with pytest.raises(pypim.InvalidConfigurationError) as exc:
        pypim.Configuration.from_file(config_path)

    assert message_content in str(exc)


def test_initialize_from_environment(tmp_path):
    # Arrange
    # A valid configuration file setting up the uri and metadata
    config_path = str(tmp_path / "config.json")
    config = r"""{
    "version": 1,
    "pim": {
        "uri": "dns:instancemanagement.example.com:443",
        "headers": {
            "authorization": "Bearer 007"
        },
        "tls": true
    }
}"""

    with open(config_path, "w") as f:
        f.write(config)

    # Act
    # Connect the client based on this configuration
    # and run a request
    with patch.dict(os.environ, {"ANSYS_PLATFORM_INSTANCEMANAGEMENT_CONFIG": config_path}):
        configuration = pypim.Configuration.from_environment()

    # Assert
    # The configuration was properly filled.
    assert configuration.access_token == "007"
    assert len(configuration.headers) == 0
    assert configuration.tls
