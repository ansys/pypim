"""Entrypoint for the product instance management python client library."""

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

    Returns:
        bool: True if the environment is configured to use PyPIM.
    """
    return CONFIGURATION_PATH_ENVIRONMENT_VARIABLE in os.environ


def connect() -> Client:
    """Create a PyPIM client based on the environment configuration.

    Raises:
        RuntimeError: The environment is not configured to use PyPIM

    Returns:
        Client: A PyPIM client, the main entrypoint to use this library.
    """
    if not is_configured():
        raise RuntimeError("The environment is not configured to use PyPIM.")
    return Client._from_configuration(os.environ[CONFIGURATION_PATH_ENVIRONMENT_VARIABLE])
