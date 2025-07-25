# Copyright (C) 2022 - 2025 ANSYS, Inc. and/or its affiliates.
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

"""Service class module."""

from typing import Mapping

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    Service as ServiceV1,
)
import grpc

from ansys.platform.instancemanagement.configuration import Configuration
from ansys.platform.instancemanagement.interceptor import header_adder_interceptor


class Service:
    """Provides an entry point for communicating with a remote product."""

    _uri: str
    _headers: Mapping[str, str]

    @property
    def uri(self) -> str:
        """Uniform resource indicator (URI) to reach the service.

        For gRPC, this is a valid URI following gRPC-name resolution
        syntax. For example, https://grpc.github.io/grpc/core/md_doc_naming.html.

        For HTTP or REST, this is a valid http or https URI. It is the base
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
        configuration: Configuration = None,
        **kwargs,
    ) -> grpc.Channel:
        """Build a gRPC channel communicating with the product instance.

        Parameters
        -----------
        configuration: pim configuration
        kwargs: list, optional
            Named arguments for gRPC construction.
            They are passed to ``grpc.secure_channel`` or ``grpc.insecure_channel``.

        Returns
        -------
        grpc.Channel
            gRPC channel ready to be used for communicating with the service.
        """
        headers = self.headers.items()
        interceptor = header_adder_interceptor(headers)

        if configuration is not None and configuration.tls:
            credentials = grpc.composite_channel_credentials(
                grpc.ssl_channel_credentials(),
                grpc.access_token_call_credentials(configuration.access_token),
            )
            channel = grpc.secure_channel(self.uri, credentials, **kwargs)
        else:
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
