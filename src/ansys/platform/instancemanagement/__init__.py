"""Entrypoint for the product instance management python client library."""

try:
    import importlib.metadata as importlib_metadata
except ModuleNotFoundError:
    import importlib_metadata

__version__ = importlib_metadata.version(__name__.replace(".", "-"))

from ansys.platform.instancemanagement.client import Client
from ansys.platform.instancemanagement.definition import Definition
