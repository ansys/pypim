"""Service class module."""

from dataclasses import dataclass
from typing import Mapping

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    Service as ServiceV1,
)
import grpc

from ansys.platform.instancemanagement.interceptor import header_adder_interceptor


@dataclass(frozen=True)
class Service:
    """An entry point to communicate with a remote product.  
    """

    uri: str
    """URI to reach the service.

    For gRPC, this is a valid URI, following gRPC-name resolution
    syntax: https://grpc.github.io/grpc/core/md_doc_naming.html

    For HTTP/REST, this is a valid http or https URI. It is the base
    path of the service API.
    """

    headers: Mapping[str, str]
    """Headers necessary to communicate with the service.

    For a gRPC service, this should be translated into metadata included in
    every communication with the service.

    For a REST-like service, this should be translated into headers included in
    every communication with the service.
    """

    def _build_grpc_channel(
        self,
        **kwargs,
    ) -> grpc.Channel:
        """Build a gRPC channel communicating with the product instance.

        Parameteers
        -----------
        kwargs: list, optional
            Named arguments for gRPC construction.
            They are passed to ``grpc.insecure_channel``.

        Returns
        -------
        grpc.Channel
            gRPC channel ready to be used for communicating with the service.
        """
        headers = self.headers.items()
        interceptor = header_adder_interceptor(headers)
        channel = grpc.insecure_channel(self.uri, **kwargs)
        return grpc.intercept_channel(channel, interceptor)

    @staticmethod
    def _from_pim_v1(service: ServiceV1):
        """Build a definition from the PIM API v1 protobuf object.

        Parameters
        ----------
        service : ServiceV1
            Raw PIM API v1 protobuf object.       

        Returns
        -------
        type
            PyPIM service definition.
        
        Raises
        ------
        ValueError: The raw protobuf message is not valid.
        """
        if not service.uri:
            raise ValueError("A service must have an URI.")

        return Service(uri=service.uri, headers=service.headers)
