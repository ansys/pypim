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

from unittest.mock import patch

import grpc
import pytest

from ansys.platform.instancemanagement._channel import (
    build_cyberchannel,
    parse_host_port,
    parse_uds_socket_path,
)


@pytest.mark.parametrize(
    "uri,expected",
    [
        ("dns:host:50052", ("host", "50052")),
        ("dns:///host:50052", ("host", "50052")),
        ("dns://authority/host:50052", ("host", "50052")),
        ("dns://host:50052", ("host", "50052")),
        ("ipv4:127.0.0.1:50052", ("127.0.0.1", "50052")),
        ("127.0.0.1:50052", ("127.0.0.1", "50052")),
        ("ipv6:[::1]:50052", ("[::1]", "50052")),
    ],
)
def test_parse_host_port(uri, expected):
    assert parse_host_port(uri) == expected


@pytest.mark.parametrize("uri", ["no-port-here", "dns:host:", "dns:host"])
def test_parse_host_port_invalid(uri):
    with pytest.raises(ValueError):
        parse_host_port(uri)


@pytest.mark.parametrize(
    "uri,expected",
    [
        ("unix:/tmp/x.sock", "/tmp/x.sock"),
        ("unix:///tmp/x.sock", "/tmp/x.sock"),
    ],
)
def test_parse_uds_socket_path(uri, expected):
    assert parse_uds_socket_path(uri) == expected


@pytest.mark.parametrize("uri", ["dns:host:port", "/tmp/x.sock"])
def test_parse_uds_socket_path_invalid(uri):
    with pytest.raises(ValueError):
        parse_uds_socket_path(uri)


@patch("ansys.platform.instancemanagement._channel.create_channel")
def test_build_cyberchannel_uds(mock_create):
    mock_create.return_value = grpc.insecure_channel("localhost:0")

    build_cyberchannel("uds", "unix:/tmp/x.sock")

    args, kwargs = mock_create.call_args
    assert args[0] == "uds"
    assert kwargs["uds_fullpath"] == "/tmp/x.sock"
    assert kwargs["grpc_options"] is None


@patch("ansys.platform.instancemanagement._channel.create_channel")
def test_build_cyberchannel_host_port_transports(mock_create):
    mock_create.return_value = grpc.insecure_channel("localhost:0")

    build_cyberchannel("wnua", "dns:host:50052")

    args, kwargs = mock_create.call_args
    assert args[0] == "wnua"
    assert kwargs["host"] == "host"
    assert kwargs["port"] == "50052"


@patch("ansys.platform.instancemanagement._channel.create_channel")
def test_build_cyberchannel_mtls_passes_certs(mock_create):
    from ansys.tools.common.cyberchannel import CertificateFiles

    mock_create.return_value = grpc.insecure_channel("localhost:0")
    certs = CertificateFiles(cert_file="c.crt", key_file="c.key", ca_file="ca.crt")

    build_cyberchannel("mtls", "dns:host:50052", cert_files=certs, certs_dir="/certs")

    args, kwargs = mock_create.call_args
    assert args[0] == "mtls"
    assert kwargs["cert_files"] is certs
    assert kwargs["certs_dir"] == "/certs"


@patch("ansys.platform.instancemanagement._channel.create_channel")
def test_build_cyberchannel_passes_options(mock_create):
    mock_create.return_value = grpc.insecure_channel("localhost:0")
    options = [("grpc.max_receive_message_length", 1234)]

    build_cyberchannel("insecure", "dns:host:50052", grpc_options=options)

    _, kwargs = mock_create.call_args
    assert kwargs["grpc_options"] == options
