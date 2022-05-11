from concurrent.futures import ThreadPoolExecutor
from unittest.mock import call, create_autospec

from ansys.api.platform.instancemanagement.v1 import product_instance_manager_pb2 as pb2
from ansys.api.platform.instancemanagement.v1 import product_instance_manager_pb2_grpc as pb2_grpc
from google.protobuf.empty_pb2 import Empty
import grpc
from grpc import StatusCode
import grpc_testing
import pytest

import ansys.platform.instancemanagement as pypim
from conftest import CREATE_INSTANCE_METHOD, DELETE_INSTANCE_METHOD, GET_INSTANCE_METHOD


def test_from_pim_v1_proto():
    instance = pypim.Instance._from_pim_v1(
        pb2.Instance(
            name="instances/my-instance",
            definition_name="definitions/my-definition",
            ready=False,
            status_message="not yet ready",
            services={
                "grpc": pb2.Service(uri="dns://some-service:651", headers={"token": "hello-world"}),
                "http": pb2.Service(
                    uri="https://some-service:651", headers={"token": "hello-world"}
                ),
            },
        )
    )
    assert instance.name == "instances/my-instance"
    assert instance.definition_name == "definitions/my-definition"
    assert not instance.ready
    assert instance.status_message == "not yet ready"
    assert instance.services == {
        "grpc": pypim.Service(uri="dns://some-service:651", headers={"token": "hello-world"}),
        "http": pypim.Service(uri="https://some-service:651", headers={"token": "hello-world"}),
    }


def test_create(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
):
    # Arrange
    # A server returning an instance
    def server():
        _, creation_request, rpc = testing_channel.take_unary_unary(CREATE_INSTANCE_METHOD)
        response = pb2.Instance(
            name="instances/hello-world-32",
            definition_name="definitions/my-def",
            ready=False,
            status_message="loading...",
            services={},
        )
        rpc.terminate(response, [], StatusCode.OK, "")
        return creation_request

    server_future = testing_pool.submit(server)

    # A client creating an instance

    # Act
    # Create an instance from the client
    stub = pb2_grpc.ProductInstanceManagerStub(testing_channel)
    instance = pypim.Instance._create(definition_name="definitions/my-def", stub=stub, timeout=0.1)

    # Assert
    # The server got the correct request
    received_creation_request = server_future.result()
    expected_creation_request = pb2.CreateInstanceRequest(
        instance=pb2.Instance(definition_name="definitions/my-def")
    )
    assert (
        received_creation_request == expected_creation_request
    ), "The request to create an instance did not match what was expected"

    # The instance was created as expected
    expected_instance = pypim.Instance(
        name="instances/hello-world-32",
        definition_name="definitions/my-def",
        ready=False,
        status_message="loading...",
        services={},
    )
    assert (
        instance == expected_instance
    ), "The response to create an instance was not correctly translated"


def test_delete(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
):
    # Arrange
    # A server watching for delete requests
    def server():
        _, deletion_request, rpc = testing_channel.take_unary_unary(DELETE_INSTANCE_METHOD)
        response = Empty()
        rpc.terminate(response, [], StatusCode.OK, "")
        return deletion_request

    server_future = testing_pool.submit(server)

    # An instance
    stub = pb2_grpc.ProductInstanceManagerStub(testing_channel)
    instance = pypim.Instance(
        name="instances/hello-world-32",
        definition_name="definitions/my-def",
        ready=False,
        status_message="loading...",
        services={},
        stub=stub,
    )

    # Act
    # Delete the instance
    instance.delete()

    # Assert
    # The server got the request for the correct instance
    received_deletion_request = server_future.result()
    expected_deletion_request = pb2.DeleteInstanceRequest(name="instances/hello-world-32")
    assert (
        received_deletion_request == expected_deletion_request
    ), "The request to create an instance did not match what was expected"


def test_context_manager(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
):
    # Arrange
    # A server returning an instance and deleting it
    def server():
        _, creation_request, rpc = testing_channel.take_unary_unary(CREATE_INSTANCE_METHOD)
        response = pb2.Instance(
            name="instances/hello-world-32",
            definition_name="definitions/my-def",
            ready=False,
            status_message="loading...",
            services={},
        )
        rpc.terminate(response, [], StatusCode.OK, "")
        _, deletion_request, rpc = testing_channel.take_unary_unary(DELETE_INSTANCE_METHOD)
        response = pb2.Instance(
            name="instances/hello-world-32",
            definition_name="definitions/my-def",
            ready=False,
            status_message="loading...",
            services={},
        )
        rpc.terminate(response, [], StatusCode.OK, "")
        return creation_request, deletion_request

    server_future = testing_pool.submit(server)

    # Act
    # Create an instance from the client with the `with` statement
    stub = pb2_grpc.ProductInstanceManagerStub(testing_channel)
    with pypim.Instance._create(
        definition_name="definitions/my-def", stub=stub, timeout=0.1
    ) as instance:
        pass

    # Assert
    # The server got the correct requests
    received_creation_request, received_deletion_request = server_future.result()
    assert received_creation_request == pb2.CreateInstanceRequest(
        instance=pb2.Instance(definition_name="definitions/my-def")
    ), "The request to create an instance did not match what was expected"
    assert received_deletion_request == pb2.DeleteInstanceRequest(name="instances/hello-world-32")

    # The instance was created as expected
    expected_instance = pypim.Instance(
        name="instances/hello-world-32",
        definition_name="definitions/my-def",
        ready=False,
        status_message="loading...",
        services={},
    )
    assert (
        instance == expected_instance
    ), "The response to create an instance was not correctly translated"


def test_update(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
):
    # Arrange
    # A server serving a hardcoded instance on GetInstance, and the corresponding pypim instance
    def server():
        _, update_request, rpc = testing_channel.take_unary_unary(GET_INSTANCE_METHOD)
        response = pb2.Instance(
            name="instances/hello-world-32",
            definition_name="definitions/my-def",
            ready=True,
            status_message=None,
            services={"http": pb2.Service(uri="http://example.com")},
        )
        rpc.terminate(response, [], StatusCode.OK, "")
        return update_request

    server_future = testing_pool.submit(server)

    stub = pb2_grpc.ProductInstanceManagerStub(testing_channel)
    instance = pypim.Instance(
        name="instances/hello-world-32",
        definition_name="definitions/my-def",
        ready=False,
        status_message="loading...",
        services={},
        stub=stub,
    )

    # Act
    # Update the instance
    instance.update(timeout=0.1)

    #  Assert
    # The server got the correct GetInstance request
    received_get_request = server_future.result()
    expected_get_request = pb2.GetInstanceRequest(name="instances/hello-world-32")
    assert received_get_request == expected_get_request

    # The instance is correctly updated
    expected_updated_instance = pypim.Instance(
        name="instances/hello-world-32",
        definition_name="definitions/my-def",
        ready=True,
        status_message="",
        services={"http": pypim.Service(uri="http://example.com", headers={})},
    )

    assert instance == expected_updated_instance


def test_update_notfound(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
):
    # Arrange
    # A server serving a 404 on GetInstance
    def server():
        _, update_request, rpc = testing_channel.take_unary_unary(GET_INSTANCE_METHOD)
        rpc.terminate(None, [], StatusCode.NOT_FOUND, "")
        return update_request

    testing_pool.submit(server)

    # An instance
    stub = pb2_grpc.ProductInstanceManagerStub(testing_channel)
    instance = pypim.Instance(
        name="instances/hello-world-32",
        definition_name="definitions/my-def",
        ready=False,
        status_message="Loading...",
        services={},
        stub=stub,
    )

    # Act
    # Update the instance
    with pytest.raises(pypim.InstanceNotFoundError) as exc:
        instance.update()

    # Assert
    # The user gets a useful error
    assert "instances/hello-world-32" in str(exc)
    assert "deleted" in str(exc)
    # And can inspect the inner error
    assert exc.value.__cause__.code() == grpc.StatusCode.NOT_FOUND


def test_update_error(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
):
    # Arrange
    # A server serving a 500 on GetInstance
    def server():
        _, update_request, rpc = testing_channel.take_unary_unary(GET_INSTANCE_METHOD)
        rpc.terminate(None, [], StatusCode.INTERNAL, "I'm a teapot.")
        return update_request

    testing_pool.submit(server)

    # An instance
    stub = pb2_grpc.ProductInstanceManagerStub(testing_channel)
    instance = pypim.Instance(
        name="instances/hello-world-32",
        definition_name="definitions/my-def",
        ready=False,
        status_message="Loading...",
        services={},
        stub=stub,
    )

    # Act
    # Update the instance
    with pytest.raises(pypim.RemoteError) as exc:
        instance.update()

    # Assert
    # The user got the server message
    assert "I'm a teapot." in str(exc)
    # And can inspect the inner error
    assert exc.value.__cause__.code() == grpc.StatusCode.INTERNAL


def test_wait_for_ready(testing_channel):
    # Arrange
    # A mocked instance where the update will not be ready
    # until three update calls
    stub = pb2_grpc.ProductInstanceManagerStub(testing_channel)
    instance = pypim.Instance(
        name="instances/hello-world-32",
        definition_name="definitions/my-def",
        ready=False,
        status_message="Creating...",
        services={},
        stub=stub,
    )

    def update_side_effect(timeout):
        timeout  # unused
        if instance.update.call_count == 0 or instance.update.call_count == 1:
            instance._ready = False
            instance._status_message = "Loading..."
        if instance.update.call_count == 2:
            instance._ready = False
            instance._status_message = "Routing..."
        if instance.update.call_count > 2:
            instance._ready = True
            instance._status_message = ""
            instance._services = {"http": pb2.Service(uri="http://example.com", headers={})}

    instance.update = create_autospec(instance.update)
    instance.update.side_effect = update_side_effect

    # Act
    # Wait for the instance to be ready
    instance.wait_for_ready(polling_interval=0.0)

    # Assert
    # The update was called three times
    instance.update.assert_has_calls([call(timeout=None), call(timeout=None), call(timeout=None)])
    # And the instance is now ready
    assert instance.ready
    assert instance.status_message == ""
    assert instance.services == {"http": pb2.Service(uri="http://example.com", headers={})}


def test_create_channel():
    # Arrange
    # Two mocked services
    main_service = pypim.Service(uri="dns:example.com", headers={})
    main_channel = grpc.insecure_channel("dns:example.com")
    main_service._build_grpc_channel = create_autospec(
        main_service._build_grpc_channel, return_value=main_channel
    )

    sidecar_service = pypim.Service(uri="dns:ansysapis.com", headers={})
    sidecar_channel = grpc.insecure_channel("dns:ansysapis.com")
    sidecar_service._build_grpc_channel = create_autospec(
        sidecar_service._build_grpc_channel, return_value=sidecar_channel
    )

    # An instance containing these services
    instance = pypim.Instance(
        name="instances/hello-world-32",
        definition_name="definitions/my-def",
        ready=True,
        status_message="Creating...",
        services={"grpc": main_service, "other": sidecar_service},
    )

    # Act: Create two channels
    channel1 = instance.build_grpc_channel()
    channel2 = instance.build_grpc_channel(service_name="other")

    # Assert: The services were called
    main_service._build_grpc_channel.assert_called_once()
    sidecar_service._build_grpc_channel.assert_called_once()
    assert channel1 == main_channel
    assert channel2 == sidecar_channel


def test_create_channel_not_ready():
    # Arrange
    # An instance that's not ready
    instance = pypim.Instance(
        name="instances/hello-world-32",
        definition_name="definitions/my-def",
        ready=False,
        status_message="Creating...",
        services={},
    )

    # Act
    # Attempt to create a channel
    with pytest.raises(pypim.InstanceNotReadyError) as exc:
        instance.build_grpc_channel()

    # Assert
    # The exception was raised with a descriptive error
    assert "instances/hello-world-32" in str(exc)


def test_create_channel_not_supported():
    # Arrange
    # An instance that does not support grpc
    instance = pypim.Instance(
        name="instances/hello-world-32",
        definition_name="definitions/my-def",
        ready=True,
        status_message=None,
        services={
            "http": pypim.Service(uri="http://example.com", headers={}),
        },
    )

    # Act
    # Attempt to create a channel
    with pytest.raises(pypim.UnsupportedServiceError) as exc:
        instance.build_grpc_channel()

    # Assert
    # The exception was raised with a descriptive error
    assert "instances/hello-world-32" in str(exc)
    assert "grpc" in str(exc)


def test_str():
    instance_str = str(
        pypim.Instance(
            name="instances/hello-world-32",
            definition_name="definitions/my-def",
            ready=False,
            status_message="Loading.",
            services={
                "my-http": pypim.Service(uri="http://example.com", headers={}),
            },
        )
    )
    assert "instances/hello-world-32" in instance_str
    assert "definitions/my-def" in instance_str
    assert "False" in instance_str
    assert "Loading." in instance_str
    assert "my-http" in instance_str
    assert "http://example.com" in instance_str


def test_repr():
    from ansys.platform.instancemanagement import Instance, Service  # noqa

    instance = pypim.Instance(
        name="instances/hello-world-32",
        definition_name="definitions/my-def",
        ready=False,
        status_message="Loading.",
        services={
            "my-http": pypim.Service(uri="http://example.com", headers={}),
        },
    )
    instance_repr = eval(repr(instance))
    assert instance == instance_repr
