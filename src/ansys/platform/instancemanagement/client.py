"""Client class module."""
import json
import logging
from typing import Sequence

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    ListDefinitionsRequest,
)
from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2_grpc import (
    ProductInstanceManagerStub,
)
import grpc

from ansys.platform.instancemanagement.definition import Definition
from ansys.platform.instancemanagement.instance import Instance
from ansys.platform.instancemanagement.interceptor import header_adder_interceptor

logger = logging.getLogger(__name__)


class Client:
    """High level client object to interact with the product instance management API.

    This class exposes the methods of the product instance management API.
    """

    _channel: grpc.Channel
    _stub: ProductInstanceManagerStub

    def __init__(self, channel: grpc.Channel) -> None:
        """Initialize the client library.

        Args:
            channel: gRPC channel hosting the connection.
        """
        logger.debug("Connecting")
        self._channel = channel
        self._stub = ProductInstanceManagerStub(self._channel)

    @staticmethod
    def _from_configuration(config_path: str):
        """Initialize a client based on the configuration file.

        Args:
            config_path (str): Path of the configuration file.

        Returns:
            Client: The PyPIM client.
        """
        logger.debug("Initializing from the configuration")

        # Note: this configuration should likely become a full featured object
        # to be shared across PyPIM class at some point.
        # The configuration is a plain json file with the settings to create the
        # grpc channel.

        with open(config_path, "r") as f:
            configuration = json.load(f)

        version = configuration["version"]
        if version != 1:
            raise RuntimeError(
                f"The file configuration version {version} is not supported.\
Consider upgrading ansys-platform-instancemanagement"
            )

        pim_configuration = configuration["pim"]
        tls = pim_configuration["tls"]
        if tls:
            raise RuntimeError(f"Secured connection is not yet supported.")

        uri = pim_configuration["uri"]
        headers = [(key, value) for key, value in pim_configuration["headers"].items()]
        channel = grpc.intercept_channel(
            grpc.insecure_channel(uri), header_adder_interceptor(headers)
        )
        return Client(channel)

    def definitions(
        self,
        product_name: str = None,
        product_version: str = None,
        timeout: float = None,
    ) -> Sequence[Definition]:
        """Get the list of supported product definitions.

        Args:
            product_name (str, optional): Filter by product name if provided.
            product_version (str, optional): Filter by product version if provided.
            timeout (float, optional): Set a timeout in seconds for the request if provided.

        Returns:
            Mapping[str, Definition]: The supported product definitions by name.
        """
        logger.debug(
            "Listing definitions for the product %s in version %s",
            product_name,
            product_version,
        )
        request = ListDefinitionsRequest(product_name=product_name, product_version=product_version)
        response = self._stub.ListDefinitions(request, timeout=timeout)
        return [
            Definition._from_pim_v1(definition, self._stub) for definition in response.definitions
        ]

    def create_instance(
        self,
        product_name: str,
        product_version: str = None,
        requests_timeout: float = None,
    ) -> Instance:
        """Create a remote instance of a product based on its name and optionally its version.

        The created instance will not yet be ready to use, you need to call `.wait_for_ready()`
        to wait for it to be ready.

        Args:
            product_name (str): Name of the product to start (eg. "mapdl")
            product_version (str, optional): Version of the product (eg. "222"). Defaults to None.
            requests_timeout (float, optional): Maximum time for each request in seconds.

        Raises:
            RuntimeError: The product and/or the selected version is not available remotely.

        Returns:
            Instance: An instance of the product.
        """
        logger.debug(
            "Creating a product instance for %s in version %s", product_name, product_version
        )
        definitions = self.definitions(
            product_name=product_name, product_version=product_version, timeout=requests_timeout
        )

        if len(definitions) == 0:
            raise RuntimeError(
                f"The remote server does not support the requested product and/or version."
            )
        definition = definitions[0]
        return definition.create_instance(timeout=requests_timeout)
