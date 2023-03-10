"""Configuration class module."""
import json
import logging
import os
import re
from typing import Sequence, Tuple

from ansys.platform.instancemanagement.exceptions import (
    InvalidConfigurationError,
    NotConfiguredError,
)

CONFIGURATION_PATH_ENVIRONMENT_VARIABLE = "ANSYS_PLATFORM_INSTANCEMANAGEMENT_CONFIG"

logger = logging.getLogger(__name__)


class Configuration:
    """Configuration for the PIM client.

    Raises:
        InvalidConfigurationError: configuration file is not a well formatted json file
        InvalidConfigurationError: version is not supported
        InvalidConfigurationError: a key is missing in the configuration file

    Returns:
        Configuration: settings to configure the PIM client
    """

    _access_token: str
    _headers: Sequence[Tuple[str, str]]
    _tls: bool
    _uri: str

    @property
    def access_token(self) -> str:
        """Access token."""
        return self._access_token

    @property
    def headers(self) -> Sequence[Tuple[str, str]]:
        """Headers to add to the requests to PIM."""
        return self._headers

    @property
    def tls(self) -> bool:
        """Whether the connection to PIM requires encryption.

        If ``True``, the ``access_token`` property is used to create a secure connection.

        If ``False``, an unsecure connection is used.
        """
        return self._tls

    @property
    def uri(self) -> str:
        """Uri of the PIM service."""
        return self._uri

    def __init__(
        self, headers: Sequence[Tuple[str, str]], tls: bool, uri: str, access_token: str
    ) -> None:
        """Initialize the PIM configuration.

        Parameters
        ----------
        tls

        headers

        """
        self._access_token = access_token
        self._headers = headers
        self._tls = tls
        self._uri = uri

    @staticmethod
    def from_file(config_path: str):
        """Initialize the PyPIM configuration based on the configuration file.

        Parameters
        ----------
        config_path : str
            Path of the configuration file.

        Returns
        -------
        Configuration
            PyPIM configuration.

        Raises
        ------
        InvalidConfigurationError
            The configuration is not valid.
        """
        logger.debug("Initializing from %s", config_path)
        with open(config_path, "r") as f:
            try:
                configuration = json.load(f)
            except json.JSONDecodeError:
                raise InvalidConfigurationError(config_path, "Invalid json.")

        # What follows should likely be done with a schema validation
        try:
            version = configuration["version"]
            if version != 1:
                raise InvalidConfigurationError(
                    config_path,
                    f'Unsupported version "{version}".\
Consider upgrading ansys-platform-instancemanagement.',
                )

            pim_configuration = configuration["pim"]
            tls = pim_configuration["tls"]
            uri = pim_configuration["uri"]
            headers = list(pim_configuration["headers"].items())
        except KeyError as key_error:
            key = key_error.args[0]
            raise InvalidConfigurationError(
                config_path, f"The configuration is missing the entry {key}."
            )

        if tls:
            logger.info("The connection to the server will use a secure channel.")
            # retrieve the first header where the key starts with 'authorization',
            # using a case insensitive comparison, and the key contains a Bearer token.
            header_authorization = next(
                filter(
                    lambda p: re.match("authorization", p[0], flags=re.IGNORECASE)
                    and re.match("Bearer ", p[1]),
                    headers,
                ),
                None,
            )
            if header_authorization is None:
                raise InvalidConfigurationError(
                    config_path,
                    "An authorization header with a bearer token is required"
                    " for a secure connection.",
                )
            access_token = header_authorization[1].replace("Bearer ", "")
            headers.remove(header_authorization)
        else:
            access_token = None
        return Configuration(headers, tls, uri, access_token)

    @staticmethod
    def from_environment():
        """Create a PyPIM configuration based on the environment configuration.

        Before calling this method, :func:`~is_configured()` should be called to check if
        the environment is configured to use PyPIM.

        The environment configuration consists in setting the environment variable
        ``ANSYS_PLATFORM_INSTANCEMANAGEMENT_CONFIG`` to the path of the PyPIM
        configuration file. The configuration file is a simple JSON file containing
        the URI of the PIM API and the headers required to pass information.

        The configuration file format is:

        .. code-block:: json

            {
                "version": 1,
                "pim": {
                    "uri": "dns:pim.svc.com:80",
                    "headers": {
                        "metadata-info": "value"
                    },
                    "tls": false
                }
            }

        Returns
        -------
        Configuration
            PyPIM configuration settings.

        Raises
        ------
        NotConfiguredError
            The environment is not configured to use PyPIM.

        InvalidConfigurationError
            The configuration is invalid.
        """
        if not is_configured():
            raise NotConfiguredError("The environment is not configured to use PyPIM.")

        return Configuration.from_file(
            os.path.expandvars(os.environ[CONFIGURATION_PATH_ENVIRONMENT_VARIABLE])
        )


def is_configured() -> bool:
    """Check if the environment is configured to use PyPIM.

    Returns
    -------
    bool
        ``True`` when the environment is configured to use PyPIM, ``False`` otherwise.
    """
    return CONFIGURATION_PATH_ENVIRONMENT_VARIABLE in os.environ
