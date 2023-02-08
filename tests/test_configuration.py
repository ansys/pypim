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
