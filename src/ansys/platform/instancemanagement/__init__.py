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

import os

from ansys.platform.instancemanagement.client import Client
from ansys.platform.instancemanagement.configuration import (
    CONFIGURATION_PATH_ENVIRONMENT_VARIABLE,
    Configuration,
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
from ansys.platform.instancemanagement.service import Service

__all__ = [
    "__version__",
    "CONFIGURATION_PATH_ENVIRONMENT_VARIABLE",
    "is_configured",
    "connect",
    "Client",
    "Configuration",
    "Instance",
    "Service",
    "Definition",
    "InstanceNotFoundError",
    "InvalidConfigurationError",
    "NotConfiguredError",
    "RemoteError",
    "UnsupportedProductError",
    "InstanceNotReadyError",
    "UnsupportedServiceError",
]

__version__ = importlib_metadata.version(__name__.replace(".", "-"))


def connect() -> Client:
    """Create a PyPIM client based on the environment configuration.

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
    Client
        PyPIM client, which is the main entry point to using this library.

    Raises
    ------
    NotConfiguredError
        The environment is not configured to use PyPIM.

    InvalidConfigurationError
        The configuration is invalid.

    Examples
    --------
        >>> import ansys.platform.instancemanagement as pypim
        >>> if pypim.is_configured():
        >>>     client = pypim.connect()
        >>>     # use the client
        >>>     client.close()

        >>> import ansys.platform.instancemanagement as pypim
        >>> if pypim.is_configured():
        >>>     with pypim.connect() as client:
        >>>         # use client
    """
    if not is_configured():
        raise NotConfiguredError("The environment is not configured to use PyPIM.")
    return Client._from_configuration(
        os.path.expandvars(os.environ[CONFIGURATION_PATH_ENVIRONMENT_VARIABLE])
    )
