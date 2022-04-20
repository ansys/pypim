"""Entry point for the PIM Python client library."""

try:
    import importlib.metadata as importlib_metadata
except ModuleNotFoundError:
    import importlib_metadata

import os

from ansys.platform.instancemanagement.client import Client
from ansys.platform.instancemanagement.definition import Definition
from ansys.platform.instancemanagement.instance import Instance
from ansys.platform.instancemanagement.service import Service

__version__ = importlib_metadata.version(__name__.replace(".", "-"))

CONFIGURATION_PATH_ENVIRONMENT_VARIABLE = "ANSYS_PLATFORM_INSTANCEMANAGEMENT_CONFIG"


def is_configured() -> bool:
    """Check if the environment is configured to use PyPIM.

    Returns
    -------
    bool
       ``True`` when successful, ``False`` when failed.
    """
    return CONFIGURATION_PATH_ENVIRONMENT_VARIABLE in os.environ


def connect() -> Client:
    """Create a PyPIM client based on the environment configuration.

    Before calling this method, ``is_configured()`` should be called to check if
    the environment is configured to use PyPIM.

    The environment configuration consists in setting the environment variable
    ``ANSYS_PLATFORM_INSTANCEMANAGEMENT_CONFIG`` to the path of the PyPIM
    configuration file. The configuration file is a simple json file containing
    the URI of the PIM API and headers required to pass information.

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
    client
        PyPIM client, which is the main entry point to using this library.

    Raises
    ------
    RuntimeError: The environment is not configured to use PyPIM.
    
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
        raise RuntimeError("The environment is not configured to use PyPIM.")
    return Client._from_configuration(os.environ[CONFIGURATION_PATH_ENVIRONMENT_VARIABLE])
