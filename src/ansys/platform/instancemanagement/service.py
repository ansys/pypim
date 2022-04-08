"""Service class module."""

from dataclasses import dataclass
from typing import Mapping

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    Service as ServiceV1,
)


@dataclass(frozen=True)
class Service:
    """An entrypoint to communicate with a remote product.

    It can be used to communicate with a remote product.
    """

    uri: str
    """The URI to reach the service.

    For gRPC, this is a valid URI, following gRPC name resolution
    syntax: https://grpc.github.io/grpc/core/md_doc_naming.html

    For HTTP/REST, this is a valid http or https URI. It is the base
    path of the service API.
    """

    headers: Mapping[str, str]
    """Headers necessary to communicate with the service.

    For a gRPC service, this should be translated into metadata included in
    every communication with the service.

    For a REST-like service, this sshould be translated into headers included in
    every communication with the service.
    """

    @staticmethod
    def _from_pim_v1(service: ServiceV1):
        """Build a Definition from the PIM API v1 protobuf object.

        Args:
            service (ServiceV1): raw PIM API v1 protobuf object

        Raises:
            ValueError: The raw protobuf message is not valid

        Returns:
            Definition: The PyPIM service
        """
        if not service.uri:
            raise ValueError("A service must have an uri")

        return Service(uri=service.uri, headers=service.headers)
