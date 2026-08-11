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

"""Entry point for the PIM Python client library."""

try:
    import importlib.metadata as importlib_metadata
except ModuleNotFoundError:
    import importlib_metadata
import logging
import os

from ansys.platform.instancemanagement.client import Client
from ansys.platform.instancemanagement.configuration import (
    CONFIGURATION_PATH_ENVIRONMENT_VARIABLE,
    Configuration,
    ConnectionSecurity,
    is_configured,
)
from ansys.platform.instancemanagement.definition import Definition
from ansys.platform.instancemanagement.exceptions import (
    InstanceNotFoundError,
    InstanceNotReadyError,
    InvalidConfigurationError,
    NotConfiguredError,
    RemoteError,
    UnsupportedProductError,
    UnsupportedServiceError,
)
from ansys.platform.instancemanagement.instance import Instance
from ansys.platform.instancemanagement.security import (
    InsecureSettings,
    MtlsCertificatePaths,
    MtlsSettings,
    SecuritySettings,
    UdsSettings,
    WnuaSettings,
)
from ansys.platform.instancemanagement.service import Service, ServiceSecurity

__all__ = [
    "__version__",
    "CONFIGURATION_PATH_ENVIRONMENT_VARIABLE",
    "is_configured",
    "connect",
    "Client",
    "Configuration",
    "ConnectionSecurity",
    "Instance",
    "Service",
    "Definition",
    "InsecureSettings",
    "WnuaSettings",
    "MtlsSettings",
    "MtlsCertificatePaths",
    "UdsSettings",
    "SecuritySettings",
    "ServiceSecurity",
    "InstanceNotFoundError",
    "InvalidConfigurationError",
    "NotConfiguredError",
    "RemoteError",
    "UnsupportedProductError",
    "InstanceNotReadyError",
    "UnsupportedServiceError",
]

__version__ = importlib_metadata.version(__name__.replace(".", "-"))

logger = logging.getLogger(__name__)


def connect(
    uri: str | None = None,
    headers: dict | None = None,
    security: "ConnectionSecurity | None" = None,
) -> Client:
    """Create a PyPIM client from the environment or from parameters.

    Precedence is parameter-first and all-or-nothing: when ``uri`` is
    provided, the configuration file is ignored in full and the client is
    built from ``uri`` / ``headers`` / ``security``. Otherwise, when the
    environment is configured (:func:`is_configured` is ``True``), the
    configuration file is used in full.

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

    A version 2 file replaces ``tls`` with a ``security`` block selecting the
    transport. See :ref:`security` for the version 2 schema and for
    programmatic configuration with the ``security`` parameter below.

    Parameters
    ----------
    uri : str, optional
        PIM gRPC service URI. When provided, it takes precedence over the
        configuration file and all settings are taken from ``uri`` /
        ``headers`` / ``security``.
    headers : dict, optional
        Metadata headers. The default is ``None`` (no headers).
    security : ConnectionSecurity, optional
        Transport security. The default is ``None`` (insecure).

    Returns
    -------
    Client
        PyPIM client, which is the main entry point to using this library.

    Raises
    ------
    NotConfiguredError
        There is neither a configuration file nor a ``uri`` parameter.

    InvalidConfigurationError
        The configuration is invalid.

    Examples
    --------
        >>> import ansys.platform.instancemanagement as pypim
        >>> if pypim.is_configured():
        >>>     client = pypim.connect()
        >>> # use the client
        >>>     client.close()

        >>> import ansys.platform.instancemanagement as pypim
        >>> if pypim.is_configured():
        >>>     with pypim.connect() as client:
        >>> # use client

        Connect programmatically with mTLS (no configuration file):

        >>> import ansys.platform.instancemanagement as pypim
        >>> from ansys.platform.instancemanagement import ConnectionSecurity
        >>> from ansys.tools.common.cyberchannel import CertificateFiles
        >>> client = pypim.connect(
        ...     uri="dns:pim.svc.com:80",
        ...     headers={"identity": "james"},
        ...     security=ConnectionSecurity(
        ...         transport="mtls",
        ...         cert_files=CertificateFiles(
        ...             cert_file="client.crt", key_file="client.key", ca_file="ca.crt"
        ...         ),
        ...     ),
        ... )
    """
    if uri is not None:
        if is_configured():
            logger.warning(
                "The configuration file %s is present and the 'uri' parameter is provided. "
                "The 'uri' parameter will be used and the configuration file will be ignored.",
                os.path.expandvars(os.environ[CONFIGURATION_PATH_ENVIRONMENT_VARIABLE]),
            )
        configuration = Configuration.from_parameters(uri=uri, headers=headers, security=security)
        return Client._from_config_object(configuration)
    if is_configured():
        return Client._from_configuration(
            os.path.expandvars(os.environ[CONFIGURATION_PATH_ENVIRONMENT_VARIABLE])
        )
    raise NotConfiguredError(
        "No PyPIM configuration file is set and no 'uri' parameter was provided."
    )
