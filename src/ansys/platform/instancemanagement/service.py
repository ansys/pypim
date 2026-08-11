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
from ansys.platform.instancemanagement._channel import build_cyberchannel
from ansys.platform.instancemanagement.configuration import Configuration
from ansys.platform.instancemanagement.interceptor import header_adder_interceptor
from ansys.tools.common.cyberchannel import CertificateFiles


@dataclass(frozen=True)
class ServiceSecurity:
    """Protobuf-free view of the server-resolved security info.

    Reports the transport the PIM server actually chose for a service, as
    opposed to the transport requested via ``security_settings`` at instance
    creation. See :ref:`security`.
    """

    transport: str
    cert_files: Optional[CertificateFiles] = None


class Service:
    """Provides an entry point for communicating with a remote product."""

    _uri: str
    _headers: Mapping[str, str]
    _security: Optional[ServiceSecurity] = None

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

    @property
    def transport(self) -> Optional[str]:
        """Transport mode resolved from the server security info.

        One of ``"mtls"``, ``"uds"``, ``"insecure"``, ``"wnua"``, or ``None``
        when no security info was provided by the server.
        """
        return self._security.transport if self._security is not None else None

    def __init__(
        self,
        uri: str,
        headers: Mapping[str, str],
        security: Optional[ServiceSecurity] = None,
    ):
        """Initialize a Service.

        Parameters
        ----------
        uri : str
            URI used to reach the service.
        headers : Mapping[str, str]
            Headers to include in every request to the service.
        security : ServiceSecurity, optional
            Server-resolved security info. The default is ``None``.
        """
        self._uri = uri
        self._headers = headers
        self._security = security

    def __eq__(self, obj):
        """Test for equality."""
        return (
            isinstance(obj, Service)
            and obj.uri == self.uri
            and obj.headers == self.headers
            and obj.transport == self.transport
        )

    def __repr__(self):
        """Python callable representation."""
        return f"Service(uri={self.uri!r}, headers={self.headers!r}, security={self._security!r})"

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
        headers = self.headers.items()
        interceptor = header_adder_interceptor(headers)

        if self._security is not None:
            channel = build_cyberchannel(
                self._security.transport,
                self.uri,
                cert_files=self._security.cert_files,
                grpc_options=kwargs.get("options"),
            )
            return grpc.intercept_channel(channel, interceptor)

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
            security = ServiceSecurity(
                transport="mtls",
                cert_files=CertificateFiles(
                    cert_file=mtls.client_certificate_path,
                    key_file=mtls.client_key_path,
                    ca_file=mtls.ca_certificate_path,
                ),
            )
        elif transport is not None:
            security = ServiceSecurity(transport=transport)
        return Service(uri=service.uri, headers=service.headers, security=security)
