from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, call

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    CreateInstanceRequest,
    DeleteInstanceRequest,
    GetInstanceRequest,
)
from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    Instance as InstanceV1,
)
from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    Service as ServiceV1,
)
from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2_grpc import (
    ProductInstanceManagerStub,
)
from google.protobuf.empty_pb2 import Empty
import grpc
from grpc import StatusCode
import grpc_testing
import pytest

from ansys.platform.instancemanagement import Instance, Service
from conftest import CREATE_INSTANCE_METHOD, DELETE_INSTANCE_METHOD, GET_INSTANCE_METHOD


def test_from_pim_v1_proto():
    instance = Instance._from_pim_v1(
        InstanceV1(
            name="instances/my-instance",
            definition_name="definitions/my-definition",
            ready=False,
            status_message="not yet ready",
            services={
                "grpc": ServiceV1(uri="dns://some-service:651", headers={"token": "hello-world"}),
                "http": ServiceV1(uri="https://some-service:651", headers={"token": "hello-world"}),
            },
        )
    )
    assert instance.name == "instances/my-instance"
    assert instance.definition_name == "definitions/my-definition"
    assert not instance.ready
    assert instance.status_message == "not yet ready"
    assert instance.services == {
        "grpc": Service(uri="dns://some-service:651", headers={"token": "hello-world"}),
        "http": Service(uri="https://some-service:651", headers={"token": "hello-world"}),
    }


@pytest.mark.parametrize(
    "invalid_instance",
    [
        InstanceV1(
            name="bad-name",
            definition_name="definitions/my-definition",
            ready=False,
            status_message="not yet ready",
            services={
                "grpc": ServiceV1(uri="dns://some-service:651", headers={"token": "hello-world"}),
                "http": ServiceV1(uri="https://some-service:651", headers={"token": "hello-world"}),
            },
        ),
        InstanceV1(
            name="instances/my-instance",
            definition_name=None,
            ready=False,
            status_message="not yet ready",
            services={
                "grpc": ServiceV1(uri="dns://some-service:651", headers={"token": "hello-world"}),
                "http": ServiceV1(uri="https://some-service:651", headers={"token": "hello-world"}),
            },
        ),
        InstanceV1(
            name="instances/my-instance",
            definition_name="bad-name",
            ready=False,
            status_message="not yet ready",
            services={
                "grpc": ServiceV1(uri="dns://some-service:651", headers={"token": "hello-world"}),
                "http": ServiceV1(uri="https://some-service:651", headers={"token": "hello-world"}),
            },
        ),
    ],
)
def test_from_pim_v1_proto_value_error(invalid_instance):
    with pytest.raises(ValueError):
        Instance._from_pim_v1(invalid_instance)


def test_create(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
):
    def client():
        stub = ProductInstanceManagerStub(testing_channel)
        return Instance._create(definition_name="definitions/my-def", stub=stub, timeout=0.1)

    def server():
        _, creation_request, rpc = testing_channel.take_unary_unary(CREATE_INSTANCE_METHOD)
        response = InstanceV1(
            name="instances/hello-world-32",
            definition_name="definitions/my-def",
            ready=False,
            status_message="loading...",
            services={},
        )
        rpc.terminate(response, [], StatusCode.OK, "")
        return creation_request

    client_future = testing_pool.submit(client)
    server_future = testing_pool.submit(server)

    instance = client_future.result()
    received_creation_request = server_future.result()

    expected_creation_request = CreateInstanceRequest(
        instance=InstanceV1(definition_name="definitions/my-def")
    )

    expected_instance = Instance(
        name="instances/hello-world-32",
        definition_name="definitions/my-def",
        ready=False,
        status_message="loading...",
        services={},
    )

    assert (
        received_creation_request == expected_creation_request
    ), "The request to create an instance did not match what was expected"
    assert (
        instance == expected_instance
    ), "The response to create an instance was not correctly translated"


def test_delete(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
):
    def client():
        stub = ProductInstanceManagerStub(testing_channel)
        instance = Instance(
            name="instances/hello-world-32",
            definition_name="definitions/my-def",
            ready=False,
            status_message="loading...",
            services={},
            _stub=stub,
        )
        instance.delete()

    def server():
        _, deletion_request, rpc = testing_channel.take_unary_unary(DELETE_INSTANCE_METHOD)
        response = Empty()
        rpc.terminate(response, [], StatusCode.OK, "")
        return deletion_request

    client_future = testing_pool.submit(client)
    server_future = testing_pool.submit(server)

    client_future.result()
    received_deletion_request = server_future.result()

    expected_deletion_request = DeleteInstanceRequest(name="instances/hello-world-32")

    assert (
        received_deletion_request == expected_deletion_request
    ), "The request to create an instance did not match what was expected"


def test_update(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
):
    def client():
        stub = ProductInstanceManagerStub(testing_channel)
        instance = Instance(
            name="instances/hello-world-32",
            definition_name="definitions/my-def",
            ready=False,
            status_message="loading...",
            services={},
            _stub=stub,
        )
        instance.update(timeout=0.1)
        return instance

    def server():
        _, update_request, rpc = testing_channel.take_unary_unary(GET_INSTANCE_METHOD)
        response = InstanceV1(
            name="instances/hello-world-32",
            definition_name="definitions/my-def",
            ready=True,
            status_message=None,
            services={"http": ServiceV1(uri="http://example.com")},
        )
        rpc.terminate(response, [], StatusCode.OK, "")
        return update_request

    client_future = testing_pool.submit(client)
    server_future = testing_pool.submit(server)

    updated_instance = client_future.result()
    received_get_request = server_future.result()

    expected_get_request = GetInstanceRequest(name="instances/hello-world-32")
    expected_updated_instance = Instance(
        name="instances/hello-world-32",
        definition_name="definitions/my-def",
        ready=True,
        status_message="",
        services={"http": Service(uri="http://example.com", headers={})},
    )

    assert received_get_request == expected_get_request
    assert updated_instance == expected_updated_instance


def test_wait_for_ready(testing_channel):
    stub = ProductInstanceManagerStub(testing_channel)
    instance = Instance(
        name="instances/hello-world-32",
        definition_name="definitions/my-def",
        ready=False,
        status_message="Creating...",
        services={},
        _stub=stub,
    )

    def update_side_effect(timeout):
        timeout  # unused
        if instance.update.call_count == 0 or instance.update.call_count == 1:
            instance.ready = False
            instance.status_message = "Loading..."
        if instance.update.call_count == 2:
            instance.ready = False
            instance.status_message = "Routing..."
        if instance.update.call_count > 2:
            instance.ready = True
            instance.status_message = ""
            instance.services = {"http": Service(uri="http://example.com", headers={})}

    instance.update = MagicMock()
    instance.update.side_effect = update_side_effect
    instance.wait_for_ready(polling_interval=0.0)

    instance.update.assert_has_calls([call(timeout=None), call(timeout=None), call(timeout=None)])
    assert instance.ready
    assert instance.status_message == ""
    assert instance.services == {"http": Service(uri="http://example.com", headers={})}


def test_create_channel():
    # Arrange
    # Two mocked services
    main_service = Service(uri="dns:example.com", headers={})
    main_channel = grpc.insecure_channel("dns:example.com")
    object.__setattr__(main_service, "_build_grpc_channel", MagicMock(return_value=main_channel))

    sidecar_service = Service(uri="dns:ansysapis.com", headers={})
    sidecar_channel = grpc.insecure_channel("dns:ansysapis.com")
    object.__setattr__(
        sidecar_service, "_build_grpc_channel", MagicMock(return_value=sidecar_channel)
    )

    # An instance containing these services
    instance = Instance(
        name="instances/hello-world-32",
        definition_name="definitions/my-def",
        ready=True,
        status_message="Creating...",
        services={"grpc": main_service, "other": sidecar_service},
    )

    # Act: Create two channels
    channel1 = instance.build_grpc_channel()
    channel2 = instance.build_grpc_channel(service_name="other")

    # Assert: The service were called
    main_service._build_grpc_channel.assert_called_once()
    sidecar_service._build_grpc_channel.assert_called_once()
    assert channel1 == main_channel
    assert channel2 == sidecar_channel
