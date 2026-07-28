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

"""Service class module."""

from dataclasses import dataclass
from typing import Mapping, Optional

import grpc

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    Service as ServiceV1,
)
from ansys.platform.instancemanagement.configuration import Configuration
from ansys.platform.instancemanagement.interceptor import header_adder_interceptor
from ansys.tools.common.cyberchannel import CertificateFiles


def _parse_host_port(uri: str) -> tuple[str, str]:
    """Extract ``(host, port)`` from a gRPC target URI.

    Strips a leading gRPC scheme (``dns:``, ``dns://[authority]/``, ``ipv4:``,
    ``ipv6:``) and splits on the last ``:``. Raises ``ValueError`` when the URI
    has no parsable ``host:port``.
    """
    target = uri
    if target.startswith("dns://"):
        rest = target[len("dns://") :]
        target = rest.split("/", 1)[1] if "/" in rest else rest
    elif target.startswith("dns:"):
        target = target[len("dns:") :]
    elif target.startswith("ipv4:"):
        target = target[len("ipv4:") :]
    elif target.startswith("ipv6:"):
        target = target[len("ipv6:") :]

    if ":" not in target:
        raise ValueError(f"Cannot parse host and port from URI: {uri!r}")
    host, port = target.rsplit(":", 1)
    if not host or not port:
        raise ValueError(f"Cannot parse host and port from URI: {uri!r}")
    return host, port


def _parse_uds_socket_path(uri: str) -> str:
    """Extract the socket path from a ``unix:`` gRPC target URI."""
    if uri.startswith("unix://"):
        return uri[len("unix://") :]
    if uri.startswith("unix:"):
        return uri[len("unix:") :]
    return uri


@dataclass(frozen=True)
class _ServiceSecurity:
    """Internal, protobuf-free view of the server-resolved security info."""

    transport: str
    cert_files: Optional[CertificateFiles] = None


class Service:
    """Provides an entry point for communicating with a remote product."""

    _uri: str
    _headers: Mapping[str, str]
    _security: Optional["_ServiceSecurity"]

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

    def __init__(
        self,
        uri: str,
        headers: Mapping[str, str],
        security: Optional[_ServiceSecurity] = None,
    ):
        """Create a Service."""
        self._uri = uri
        self._headers = headers
        self._security = security

    def __eq__(self, obj):
        """Test for equality."""
        return isinstance(obj, Service) and obj.headers == self.headers and obj.uri == self.uri

    def __repr__(self):
        """Python callable representation."""
        return f"Service(uri={repr(self.uri)}, headers={repr(self.headers)})"

    def _build_grpc_channel(
        self,
        configuration: Configuration | None = None,
        **kwargs,
    ) -> grpc.Channel:
        """Build a gRPC channel communicating with the product instance.

        Parameters
        ----------
        configuration: Configuration | None, optional
            PIM configuration.
        **kwargs
            Keyword arguments passed to ``grpc.secure_channel`` or ``grpc.insecure_channel``.

        Returns
        -------
        grpc.Channel
            gRPC channel ready to be used for communicating with the service.
        """
        if configuration is not None and configuration.tls:
            credentials = grpc.composite_channel_credentials(
                grpc.ssl_channel_credentials(),
                grpc.access_token_call_credentials(configuration.access_token),
            )
            channel = grpc.secure_channel(self.uri, credentials, **kwargs)
        else:
            channel = grpc.insecure_channel(self.uri, **kwargs)

        headers = self.headers.items()
        interceptor = header_adder_interceptor(headers)
        return grpc.intercept_channel(channel, interceptor)

    @staticmethod
    def _from_pim_v1(service: ServiceV1) -> "Service":
        """Create a PyPIM service from the PIM API v1 raw protobuf message.

        Parameters
        ----------
        service : ServiceV1
            Raw PIM API v1 protobuf object.

        Returns
        -------
        Service
            The PyPIM service.
        """
        security = None
        transport = service.security.WhichOneof("transport")
        if transport == "mtls":
            mtls = service.security.mtls
            security = _ServiceSecurity(
                transport="mtls",
                cert_files=CertificateFiles(
                    cert_file=mtls.client_certificate_path,
                    key_file=mtls.client_key_path,
                    ca_file=mtls.ca_certificate_path,
                ),
            )
        elif transport is not None:
            security = _ServiceSecurity(transport=transport)
        return Service(uri=service.uri, headers=service.headers, security=security)
