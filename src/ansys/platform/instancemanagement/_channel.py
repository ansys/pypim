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

"""Internal gRPC channel construction for cyberchannel transports.

Shared by the client-to-PIM-server connection and the instance-service
connections. Depends only on ``grpc`` and ``ansys.tools.common.cyberchannel``.
"""

from typing import Sequence

import grpc

from ansys.tools.common.cyberchannel import CertificateFiles, create_channel

# Helpers to parse gRPC target URIs for channel construction.
# Reference: https://grpc.github.io/grpc/core/md_doc_naming.html


def parse_host_port(uri: str) -> tuple[str, str]:
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


def parse_uds_socket_path(uri: str) -> str:
    """Extract the socket path from a ``unix:`` gRPC target URI.

    Raises ``ValueError`` when the URI doesn't start with ``unix:``.
    """
    if uri.startswith("unix://"):
        return uri[len("unix://") :]
    if uri.startswith("unix:"):
        return uri[len("unix:") :]
    raise ValueError(f"Cannot parse Unix Domain Socket path from URI: {uri!r}")


def build_cyberchannel(
    transport: str,
    uri: str,
    cert_files: CertificateFiles | None = None,
    certs_dir: str | None = None,
    grpc_options: Sequence[tuple[str, object]] | None = None,
) -> grpc.Channel:
    """Build a cyberchannel gRPC channel for the given transport.

    Parameters
    ----------
    transport : str
        One of ``"uds"``, ``"mtls"``, ``"wnua"``, or ``"insecure"``.
    uri : str
        gRPC target URI. For ``uds`` a ``unix:`` target; otherwise a
        ``host:port`` target.
    cert_files : CertificateFiles, optional
        mTLS client certificate/key/CA files. The default is ``None``.
    certs_dir : str, optional
        mTLS certificates directory (alternative to ``cert_files``). The
        default is ``None``.
    grpc_options : list, optional
        gRPC channel options. The default is ``None``.

    Returns
    -------
    grpc.Channel
        Channel produced by ``cyberchannel.create_channel``.
    """
    if transport == "uds":
        return create_channel(
            "uds",
            uds_fullpath=parse_uds_socket_path(uri),
            grpc_options=grpc_options,
        )
    host, port = parse_host_port(uri)
    return create_channel(
        transport,
        host=host,
        port=port,
        cert_files=cert_files,
        certs_dir=certs_dir,
        grpc_options=grpc_options,
    )
