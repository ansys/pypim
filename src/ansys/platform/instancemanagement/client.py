"""Client class module."""
import logging
from typing import Mapping

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    ListDefinitionsRequest,
)
from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2_grpc import (
    ProductInstanceManagerStub,
)
import grpc

from ansys.platform.instancemanagement.definition import Definition

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

    def definitions(
        self,
        product_name: str = None,
        product_version: str = None,
        timeout: float = None,
    ) -> Mapping[str, Definition]:
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
        definition_list = [
            Definition._from_pim_v1(definition) for definition in response.definitions
        ]

        return {definition.name: definition for definition in definition_list}
