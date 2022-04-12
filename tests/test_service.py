from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    Service as ServiceV1,
)
import grpc
import grpc_health.v1.health_pb2 as health_pb2
import grpc_health.v1.health_pb2_grpc as health_pb2_grpc
import pytest

from ansys.platform.instancemanagement import Service


def test_from_pim_v1_proto():
    service = Service._from_pim_v1(
        ServiceV1(uri="dns://some-service", headers={"token": "some-token"})
    )
    assert service.uri == "dns://some-service"
    assert service.headers == {"token": "some-token"}


@pytest.mark.parametrize(
    "invalid_service",
    [
        ServiceV1(
            uri="",
            headers={"token": "some-token"},
        ),
    ],
)
def test_from_pim_v1_proto_value_error(invalid_service):
    with pytest.raises(ValueError):
        Service._from_pim_v1(invalid_service)


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

    service = Service(uri=f"127.0.0.1:{port}", headers=headers)

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
