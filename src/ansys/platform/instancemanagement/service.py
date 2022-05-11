"""Service class module."""

from typing import Mapping

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    Service as ServiceV1,
)
import grpc

from ansys.platform.instancemanagement.interceptor import header_adder_interceptor


class Service:
    """An entry point to communicate with a remote product."""

    _uri: str
    _headers: Mapping[str, str]

    @property
    def uri(self) -> str:
        """URI to reach the service.

        For gRPC, this is a valid URI, following gRPC-name resolution
        syntax: https://grpc.github.io/grpc/core/md_doc_naming.html

        For HTTP/REST, this is a valid http or https URI. It is the base
        path of the service API.
        """
        return self._uri

    @property
    def headers(self) -> Mapping[str, str]:
        """Headers necessary to communicate with the service.

        For a gRPC service, this should be translated into metadata included in
        every communication with the service.

        For a REST-like service, this should be translated into headers included in
        every communication with the service.
        """
        return self._headers

    def __init__(self, uri: str, headers: Mapping[str, str]):
        """Create a Service."""
        self._uri = uri
        self._headers = headers

    def __eq__(self, obj):
        """Test for equality."""
        return isinstance(obj, Service) and obj.headers == self.headers and obj.uri == self.uri

    def __repr__(self):
        """Python callable representation."""
        return f"Service(uri={repr(self.uri)}, headers={repr(self.headers)})"

    def _build_grpc_channel(
        self,
        **kwargs,
    ) -> grpc.Channel:
        """Build a gRPC channel communicating with the product instance.

        Parameters
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
        Service
            The PyPIM service
            PyPIM service definition.
        """
        return Service(uri=service.uri, headers=service.headers)
