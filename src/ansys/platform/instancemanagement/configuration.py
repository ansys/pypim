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

"""Configuration class module."""

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import re
from typing import Sequence, Tuple

from ansys.platform.instancemanagement._channel import parse_uds_socket_path
from ansys.platform.instancemanagement.exceptions import (
    InvalidConfigurationError,
    NotConfiguredError,
)
from ansys.tools.common.cyberchannel import CertificateFiles, verify_uds_socket

CONFIGURATION_PATH_ENVIRONMENT_VARIABLE = "ANSYS_PLATFORM_INSTANCEMANAGEMENT_CONFIG"

logger = logging.getLogger(__name__)

VALID_TRANSPORTS = frozenset({"insecure", "tls", "uds", "mtls", "wnua"})


def _extract_bearer_token(headers: list[Tuple[str, str]], config_path: str) -> str:
    """Pop and return the bearer token from an authorization header.

    Mutates ``headers`` in place by removing the matched header. Raises
    ``InvalidConfigurationError`` when no ``authorization: Bearer ...`` header
    is present.
    """
    header_authorization = next(
        filter(
            lambda p: (
                re.match("authorization", p[0], flags=re.IGNORECASE) and re.match("Bearer ", p[1])
            ),
            headers,
        ),
        None,
    )
    if header_authorization is None:
        raise InvalidConfigurationError(
            config_path,
            "An authorization header with a bearer token is required for a secure connection.",
        )
    headers.remove(header_authorization)
    return header_authorization[1].replace("Bearer ", "")


@dataclass(frozen=True)
class ConnectionSecurity:
    """Security settings for the client's connection to the PIM server.

    Mirrors the instance-service ``ServiceSecurity`` shape: a transport name and
    optional client certificate files. Used to configure ``connect()``
    programmatically when no configuration file is present.

    For ``mtls``, provide at most one of ``cert_files`` or ``certs_dir``.
    Providing neither is valid and lets the underlying transport layer
    resolve its own defaults, mirroring the version 2 configuration file's
    ``certificate_files`` / ``certificates_directory`` options.
    """

    transport: str = "insecure"
    cert_files: CertificateFiles | None = None
    certs_dir: str | None = None

    def __post_init__(self) -> None:
        """Validate the transport name and mTLS certificate options."""
        if self.transport not in VALID_TRANSPORTS:
            raise ValueError(
                f"Unsupported transport '{self.transport}'. "
                f"Valid options are: {', '.join(sorted(VALID_TRANSPORTS))}."
            )
        if self.cert_files is not None and self.certs_dir is not None:
            raise ValueError("Provide either 'cert_files' or 'certs_dir', not both.")


class Configuration:
    """Configuration for the PIM client.

    Raises
    ------
        InvalidConfigurationError: configuration file is not a well formatted json file
        InvalidConfigurationError: version is not supported
        InvalidConfigurationError: a key is missing in the configuration file

    Returns
    -------
        Configuration: settings to configure the PIM client
    """

    _access_token: str
    _headers: Sequence[Tuple[str, str]]
    _tls: bool
    _uri: str
    _transport: str
    _cert_files: CertificateFiles | None
    _certs_dir: str | None

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

        If ``False``, an insecure connection is used.
        """
        return self._tls

    @property
    def uri(self) -> str:
        """Uri of the PIM service."""
        return self._uri

    @property
    def transport(self) -> str:
        """Canonical transport: ``insecure``, ``tls``, ``uds``, ``mtls``, or ``wnua``."""
        return self._transport

    @property
    def cert_files(self) -> CertificateFiles | None:
        """MTLS client certificate files, or ``None``."""
        return self._cert_files

    @property
    def certs_dir(self) -> str | None:
        """MTLS certificates directory, or ``None``."""
        return self._certs_dir

    def __init__(
        self,
        headers: Sequence[Tuple[str, str]],
        tls: bool,
        uri: str,
        access_token: str | None = None,
        transport: str | None = None,
        cert_files: CertificateFiles | None = None,
        certs_dir: str | None = None,
    ) -> None:
        """Initialize the PIM configuration.

        Parameters
        ----------
        headers : Sequence[Tuple[str, str]]
            List of ``(key, value)`` pairs added to every request as metadata.
        tls : bool
            Whether the connection to PIM requires encryption. When ``True``,
            ``access_token`` is used to build the secure channel credentials.
        uri : str
            URI of the PIM gRPC service, e.g. ``dns:pim.svc.com:80``.
        access_token : str
            Bearer token extracted from the authorization header. Only used
            when ``tls`` is ``True``.
        transport : str, optional
            Canonical transport. When ``None``, derived from ``tls``
            (``"tls"`` if ``tls`` else ``"insecure"``).
        cert_files : CertificateFiles, optional
            mTLS client certificate files. The default is ``None``.
        certs_dir : str, optional
            mTLS certificates directory. The default is ``None``.
        """
        self._access_token = access_token
        self._headers = headers
        self._tls = tls
        self._uri = uri
        self._transport = transport if transport is not None else ("tls" if tls else "insecure")
        self._cert_files = cert_files
        self._certs_dir = certs_dir

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
        config_file_path = Path(config_path)
        logger.debug("Initializing from %s", config_file_path)
        with config_file_path.open("r") as f:
            try:
                configuration = json.load(f)
            except json.JSONDecodeError as e:
                raise InvalidConfigurationError(config_path, "Invalid json.") from e

        try:
            version = configuration["version"]
        except KeyError as key_error:
            raise InvalidConfigurationError(
                config_path, f"The configuration is missing the entry {key_error.args[0]}."
            )

        if version == 1:
            return Configuration._from_v1(configuration, config_path)
        if version == 2:
            return Configuration._from_v2(configuration, config_path)
        raise InvalidConfigurationError(
            config_path,
            f'Unsupported version "{version}".'
            " Consider upgrading ansys-platform-instancemanagement.",
        )

    @staticmethod
    def from_parameters(
        uri: str,
        headers: dict | None = None,
        security: "ConnectionSecurity | None" = None,
    ) -> "Configuration":
        """Build a configuration from programmatic parameters.

        Parameters
        ----------
        uri : str
            URI of the PIM gRPC service.
        headers : dict, optional
            Metadata headers. The default is ``None`` (no headers).
        security : ConnectionSecurity, optional
            Transport security. The default is ``None`` (insecure).

        Returns
        -------
        Configuration
            The resolved configuration.

        Raises
        ------
        InvalidConfigurationError
            The ``tls`` transport is selected but no bearer token header is
            present, or the ``uds`` transport is selected but ``uri`` is not
            a valid, existing UDS socket path.
        """
        header_list = list(headers.items()) if headers else []
        if security is None:
            security = ConnectionSecurity()

        access_token = None
        if security.transport == "tls":
            access_token = _extract_bearer_token(header_list, "<parameters>")
        elif security.transport == "uds":
            Configuration._validate_uds_socket(uri, "<parameters>")

        return Configuration(
            header_list,
            security.transport == "tls",
            uri,
            access_token,
            transport=security.transport,
            cert_files=security.cert_files,
            certs_dir=security.certs_dir,
        )

    @staticmethod
    def _from_v1(configuration: dict, config_path: str) -> "Configuration":
        """Parse a version 1 configuration document."""
        try:
            pim_configuration = configuration["pim"]
            tls = pim_configuration["tls"]
            uri = pim_configuration["uri"]
            headers = list(pim_configuration["headers"].items())
        except KeyError as key_error:
            raise InvalidConfigurationError(
                config_path, f"The configuration is missing the entry {key_error.args[0]}."
            )

        if tls:
            logger.info("The connection to the server will use a secure channel.")
            access_token = _extract_bearer_token(headers, config_path)
            transport = "tls"
        else:
            access_token = None
            transport = "insecure"
        return Configuration(headers, tls, uri, access_token, transport=transport)

    @staticmethod
    def _from_v2(configuration: dict, config_path: str) -> "Configuration":
        """Parse a version 2 configuration document."""
        try:
            pim_configuration = configuration["pim"]
            uri = pim_configuration["uri"]
            headers = list(pim_configuration["headers"].items())
            security = pim_configuration["security"]
            transport = security["transport"]
        except (KeyError, TypeError) as error:
            key = error.args[0] if isinstance(error, KeyError) else "pim"
            raise InvalidConfigurationError(
                config_path, f"The configuration is missing the entry {key}."
            )

        if transport not in VALID_TRANSPORTS:
            raise InvalidConfigurationError(
                config_path,
                f"Unsupported transport '{transport}'. "
                f"Valid options are: {', '.join(sorted(VALID_TRANSPORTS))}.",
            )

        access_token = None
        cert_files = None
        certs_dir = None

        if transport == "tls":
            logger.info("The connection to the server will use a secure channel.")
            access_token = _extract_bearer_token(headers, config_path)
        elif transport == "mtls":
            cert_files, certs_dir = Configuration._parse_mtls(security, config_path)
        elif transport == "uds":
            Configuration._validate_uds_socket(uri, config_path)

        return Configuration(
            headers,
            transport == "tls",
            uri,
            access_token,
            transport=transport,
            cert_files=cert_files,
            certs_dir=certs_dir,
        )

    @staticmethod
    def _validate_uds_socket(uri: str, config_path: str) -> None:
        """Validate that ``uri`` refers to an existing UDS socket path.

        Parses the socket path from ``uri`` and checks that it exists, raising
        ``InvalidConfigurationError`` (rather than a bare ``ValueError``) on
        either a malformed URI or a missing socket.
        """
        try:
            socket_path = parse_uds_socket_path(uri)
        except ValueError as error:
            raise InvalidConfigurationError(config_path, str(error)) from error
        if not verify_uds_socket(uds_fullpath=socket_path):
            raise InvalidConfigurationError(
                config_path, f"The UDS socket path {socket_path} does not exist."
            )

    @staticmethod
    def _parse_mtls(security: dict, config_path: str) -> Tuple[CertificateFiles | None, str | None]:
        """Resolve mTLS cert files/dir from a v2 security block."""
        certs_dir = security.get("certificates_directory")
        files = security.get("certificate_files")
        if certs_dir is not None and files is not None:
            raise InvalidConfigurationError(
                config_path,
                "Provide either 'certificates_directory' or 'certificate_files', not both.",
            )
        cert_files = None
        if files is not None:
            for key in ("cert_file", "key_file", "ca_file"):
                if key not in files:
                    raise InvalidConfigurationError(
                        config_path, f"The 'certificate_files' block is missing '{key}'."
                    )
            cert_files = CertificateFiles(
                cert_file=files["cert_file"],
                key_file=files["key_file"],
                ca_file=files["ca_file"],
            )
        return cert_files, certs_dir

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
