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

from ansys.api.platform.instancemanagement.v1 import product_instance_manager_pb2 as pb2
import grpc
import grpc_health.v1.health_pb2 as health_pb2
import grpc_health.v1.health_pb2_grpc as health_pb2_grpc
import pytest

import ansys.platform.instancemanagement as pypim


def test_from_pim_v1_proto():
    service = pypim.Service._from_pim_v1(
        pb2.Service(uri="dns://some-service", headers={"token": "some-token"})
    )
    assert service.uri == "dns://some-service"
    assert service.headers == {"token": "some-token"}


@pytest.mark.parametrize("headers", [{}, {"a": "b"}, {"my-token": "value", "identity": "thing"}])
def test_build_channel(testing_pool, headers):
    # Arrange
    # A very basic server implementing health check
    # with a Service object representing a connection to it
    server = grpc.server(testing_pool)

    received_metadata = []
    received_requests = []

    class HealthServicer(health_pb2_grpc.HealthServicer):
        def Check(self, request, context):
            received_metadata.append(context.invocation_metadata())
            received_requests.append(request)
            return health_pb2.HealthCheckResponse()

    health_pb2_grpc.add_HealthServicer_to_server(HealthServicer(), server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()

    service = pypim.Service(uri=f"127.0.0.1:{port}", headers=headers)

    # Act
    # Build a grpc channel from the service,
    # and send a message
    with service._build_grpc_channel() as channel:
        stub = health_pb2_grpc.HealthStub(channel)
        request = health_pb2.HealthCheckRequest(service="hello world")
        stub.Check(request)

    server.stop(grace=0.1)

    # Assert
    # The message was received
    # it's intact and the headers were injected.
    assert len(received_metadata) == 1
    assert len(received_requests) == 1

    # note: no assertion on length, gRPC itself injects metadata
    metadata_dict = dict(received_metadata[0])
    for header, value in headers.items():
        assert header in metadata_dict.keys()
        assert metadata_dict[header] == value

    assert received_requests[0] == health_pb2.HealthCheckRequest(service="hello world")


def test_str():
    service_str = str(pypim.Service(uri="http://example.com", headers={"hello": "world"}))
    assert "http://example.com" in service_str
    assert "hello" in service_str
    assert "world" in service_str
