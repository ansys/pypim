from concurrent.futures import ThreadPoolExecutor
import os
from unittest.mock import create_autospec, patch

from ansys.api.platform.instancemanagement.v1 import product_instance_manager_pb2 as pb2
from ansys.api.platform.instancemanagement.v1 import product_instance_manager_pb2_grpc as pb2_grpc
import grpc
from grpc import StatusCode
import grpc_testing
import pytest

import ansys.platform.instancemanagement as pypim
from conftest import GET_INSTANCE_METHOD, LIST_DEFINITIONS_METHOD, LIST_INSTANCES_METHOD


@pytest.mark.parametrize(
    ("arguments", "expected_request"),
    [
        (
            {},
            pb2.ListDefinitionsRequest(),
        ),
        (
            {"product_name": "my-product"},
            pb2.ListDefinitionsRequest(product_name="my-product"),
        ),
        (
            {"product_version": "221"},
            pb2.ListDefinitionsRequest(product_version="221"),
        ),
        (
            {"product_name": "my-product", "product_version": "221"},
            pb2.ListDefinitionsRequest(product_name="my-product", product_version="221"),
        ),
    ],
)
def test_definitions_request(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
    arguments,
    expected_request,
):
    # Arrange
    # A server watching the client request for listing definitions
    # and the pypim client
    client = pypim.Client(testing_channel)

    def server():
        _, request, rpc = testing_channel.take_unary_unary(LIST_DEFINITIONS_METHOD)
        rpc.terminate(pb2.ListDefinitionsResponse(), [], StatusCode.OK, "")
        return request

    server_future = testing_pool.submit(server)

    # Act
    # Query the list of definitions
    client.list_definitions(**arguments, timeout=1)

    # Assert
    # The server received the expected request
    assert server_future.result() == expected_request


@pytest.mark.parametrize(
    ("response", "expected_definitions"),
    [
        (
            pb2.ListDefinitionsResponse(),
            [],
        ),
        (
            pb2.ListDefinitionsResponse(
                definitions=[
                    pb2.Definition(
                        name="definitions/my-definition",
                        product_name="my-product",
                        product_version="221",
                        available_service_names=["grpc", "sidecar"],
                    ),
                    pb2.Definition(
                        name="definitions/my-other-definition",
                        product_name="my-product",
                        product_version="222",
                        available_service_names=["http"],
                    ),
                ]
            ),
            [
                pypim.Definition(
                    name="definitions/my-definition",
                    product_name="my-product",
                    product_version="221",
                    available_service_names=["grpc", "sidecar"],
                ),
                pypim.Definition(
                    name="definitions/my-other-definition",
                    product_name="my-product",
                    product_version="222",
                    available_service_names=["http"],
                ),
            ],
        ),
    ],
)
def test_list_definitions_response(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
    response,
    expected_definitions,
):
    # Arrange
    # A server providing a hardcoded list of definitions
    def server():
        _, _, rpc = testing_channel.take_unary_unary(LIST_DEFINITIONS_METHOD)
        rpc.terminate(response, [], StatusCode.OK, "")

    server_future = testing_pool.submit(server)

    # Act
    # Get the definitions
    client = pypim.Client(testing_channel)
    definitions = client.list_definitions(timeout=1)
    server_future.result()

    # Assert
    # The list of definitions were correctly received
    assert definitions == expected_definitions


def test_instances_request(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
):
    # Arrange
    # A server storing the list instance requests
    def server():
        _, request, rpc = testing_channel.take_unary_unary(LIST_INSTANCES_METHOD)
        rpc.terminate(pb2.ListInstancesResponse(), [], StatusCode.OK, "")
        return request

    server_future = testing_pool.submit(server)

    # Act
    # Get the list of instances from the client
    client = pypim.Client(testing_channel)
    client.list_instances(timeout=1)

    # Assert
    # The client sent an empty ListInstanceRequest
    assert server_future.result() == pb2.ListInstancesRequest()


def test_get_instance(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
):
    # Arrange
    # A server providing an instance
    def server():
        _, request, rpc = testing_channel.take_unary_unary(GET_INSTANCE_METHOD)
        instance = pypim.Instance._from_pim_v1(
            pb2.Instance(
                name="instances/my-instance",
                definition_name="definitions/my-definition",
                ready=False,
                status_message="not yet ready",
                services={
                    "grpc": pb2.Service(
                        uri="dns://some-service:651", headers={"token": "hello-world"}
                    ),
                    "http": pb2.Service(
                        uri="https://some-service:651", headers={"token": "hello-world"}
                    ),
                },
            )
        )
        rpc.terminate(instance, [], StatusCode.OK, "")
        return request

    server_future = testing_pool.submit(server)

    # Act
    # Get the instance from the client
    client = pypim.Client(testing_channel)
    instance = client.get_instance("instances/my-instance")

    # Assert
    # The client sent a request with the instance name
    assert server_future.result() == pb2.GetInstanceRequest(name="instances/my-instance")

    # The client created the corresponding instance object
    assert instance == pypim.Instance(
        name="instances/my-instance",
        definition_name="definitions/my-definition",
        ready=False,
        status_message="not yet ready",
        services={
            "grpc": pypim.Service(uri="dns://some-service:651", headers={"token": "hello-world"}),
            "http": pypim.Service(uri="https://some-service:651", headers={"token": "hello-world"}),
        },
    )


def test_update_notfound(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
):
    # Arrange
    # A server failing to provide instances
    def server():
        _, update_request, rpc = testing_channel.take_unary_unary(GET_INSTANCE_METHOD)
        rpc.terminate(None, [], StatusCode.NOT_FOUND, "")
        _, update_request, rpc = testing_channel.take_unary_unary(GET_INSTANCE_METHOD)
        rpc.terminate(None, [], StatusCode.INTERNAL, "I'm a teapot.")
        return update_request

    testing_pool.submit(server)

    # Act
    # Try getting the instance
    client = pypim.Client(testing_channel)
    with pytest.raises(pypim.InstanceNotFoundError) as failure1:
        client.get_instance("instances/does-not-exists")
    with pytest.raises(pypim.RemoteError) as failure2:
        client.get_instance("instances/server-error")

    # Assert
    # The user gets a useful error for the not found one
    # and inspect the inner error
    assert "instances/does-not-exists" in str(failure1)
    assert failure1.value.__cause__.code() == grpc.StatusCode.NOT_FOUND

    # The user gets the server error for the generic one
    # and inspect the inner error
    assert "I'm a teapot." in str(failure2)
    assert failure2.value.__cause__.code() == grpc.StatusCode.INTERNAL


@pytest.mark.parametrize(
    ("response", "expected_instances"),
    [
        (
            pb2.ListInstancesResponse(),
            [],
        ),
        (
            pb2.ListInstancesResponse(
                instances=[
                    pb2.Instance(
                        name="instances/hello-world-32",
                        definition_name="definitions/my-def",
                        ready=False,
                        status_message="loading...",
                        services={},
                    ),
                    pb2.Instance(
                        name="instances/hello-world-33",
                        definition_name="definitions/my-def",
                        ready=True,
                        status_message="",
                        services={"grpc": pb2.Service(uri="dns:api.com:80", headers={})},
                    ),
                ]
            ),
            [
                pypim.Instance(
                    name="instances/hello-world-32",
                    definition_name="definitions/my-def",
                    ready=False,
                    status_message="loading...",
                    services={},
                ),
                pypim.Instance(
                    name="instances/hello-world-33",
                    definition_name="definitions/my-def",
                    ready=True,
                    status_message="",
                    services={"grpc": pypim.Service(uri="dns:api.com:80", headers={})},
                ),
            ],
        ),
    ],
)
def test_list_instances_response(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
    response,
    expected_instances,
):
    # Arrange
    # A server providing a hard coded list of instances
    def server():
        _, _, rpc = testing_channel.take_unary_unary(LIST_INSTANCES_METHOD)
        rpc.terminate(response, [], StatusCode.OK, "")

    server_future = testing_pool.submit(server)

    # Act
    # Get the list of instances
    client = pypim.Client(testing_channel)
    instances = client.list_instances(timeout=1)

    #  Assert
    # The client got the hardcoded instances
    server_future.result()
    assert instances == expected_instances


def test_create_instance(testing_channel):
    # Arrange
    # A client with two definitions
    client = pypim.Client(testing_channel)
    definitions = [
        pypim.Definition(
            name="definitions/the-good-one",
            product_name="calculator",
            product_version="221",
            available_service_names=["fax"],
        ),
        pypim.Definition(
            name="definitions/the-bad-one",
            product_name="calculator",
            product_version="195",
            available_service_names=["fax"],
        ),
    ]
    instance = pypim.Instance(
        definition_name="definitions/the-good-one",
        name="instances/calculator-42",
        ready=False,
        status_message="loading...",
        services={},
    )
    definitions[0].create_instance = create_autospec(
        definitions[0].create_instance, return_value=instance
    )
    definitions[1].create_instance = create_autospec(definitions[1].create_instance)
    client.list_definitions = create_autospec(client.list_definitions, return_value=definitions)

    # Act
    created_instance = client.create_instance(
        product_name="definitions/the-good-one", requests_timeout=0.32
    )

    # Assert
    # The method created an instance from the first definition
    client.list_definitions.assert_called()
    client.list_definitions.assert_called_once_with(
        product_name="definitions/the-good-one", product_version=None, timeout=0.32
    )
    definitions[0].create_instance.assert_called_once_with(timeout=0.32)
    definitions[1].create_instance.assert_not_called()
    assert created_instance == instance


def test_unsupported_product(
    testing_channel: grpc_testing.Channel,
):
    # Arrange
    # A client mocking a server not supporting the requested products
    client = pypim.Client(testing_channel)
    client.list_definitions = create_autospec(client.list_definitions, return_value=[])

    # Act
    # Attempt to create an unsupported product
    with pytest.raises(pypim.UnsupportedProductError) as no_product_exception:
        client.create_instance(product_name="mapdl")

    # Attempt to create an unsupported version
    with pytest.raises(pypim.UnsupportedProductError) as no_version_exception:
        client.create_instance(product_name="calculator", product_version="222")

    # Assert: Got an unsupported product exception including the version when
    # requested
    assert no_product_exception.value.product_name == "mapdl"
    assert not no_product_exception.value.product_version
    assert "mapdl" in str(no_product_exception)

    assert no_version_exception.value.product_name == "calculator"
    assert no_version_exception.value.product_version == "222"
    assert "calculator" in str(no_version_exception)
    assert "222" in str(no_version_exception)


def test_initialize_from_configuration(testing_pool, tmp_path):
    # Arrange
    # A basic implementation of PIM able to list definitions
    received_metadata = []

    class PIMServicer(pb2_grpc.ProductInstanceManagerServicer):
        def ListDefinitions(self, _, context):
            received_metadata.append(context.invocation_metadata())
            return pb2.ListDefinitionsResponse()

    server = grpc.server(testing_pool)
    pb2_grpc.add_ProductInstanceManagerServicer_to_server(PIMServicer(), server)

    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    # A valid configuration file setting up the uri and metadata
    config_path = str(tmp_path / "config.json")
    config = (
        r"""{
    "version": 1,
    "pim": {
        "uri": "dns:127.0.0.1:%s",
        "headers": {
            "token": "007",
            "identity": "james bond"
        },
        "tls": false
    }
}"""
        % port
    )

    with open(config_path, "w") as f:
        f.write(config)

    # Act
    # Connect the client based on this configuration
    # and run a request
    with patch.dict(os.environ, {"ANSYS_PLATFORM_INSTANCEMANAGEMENT_CONFIG": config_path}):
        with pypim.connect() as client:
            client.list_definitions(product_name="hello-world", product_version="231")

    # Assert
    # The server got the request with the intended headers
    assert len(received_metadata) == 1
    received_metadata_dict = dict(received_metadata[0])
    assert received_metadata_dict["token"] == "007"
    assert received_metadata_dict["identity"] == "james bond"


def test_not_configured():
    with pytest.raises(pypim.NotConfiguredError):
        pypim.connect()


@pytest.mark.parametrize(
    "bad_configuration,message_content",
    [
        (r"""not even the right format""", "json"),
        (r"""{"version": 2, "pim": "future format"}""", "Unsupported version"),
        (
            r"""{"version": 1, "pim": {
                "headers": {"token": "007","identity": "james bond"},"tls": false}}""",
            "uri",
        ),
        (r"""{"version": 1, "pim": {"uri": "dns:127.0.0.1:5000","tls": false}}""", "headers"),
        (
            r"""{"version": 1, "pim": {"uri": "dns:127.0.0.1:5000",
            "headers": {"token": "007","identity": "james bond"}}}""",
            "tls",
        ),
        (
            r"""{"version": 1, "pim": {"uri": "dns:127.0.0.1:5000", "tls": true,
            "headers": {"token": "007","identity": "james bond"}}}""",
            "not yet supported",
        ),
    ],
)
def test_bad_configuration(tmp_path, bad_configuration, message_content):
    config_path = tmp_path / "pim.json"
    with open(config_path, "w") as f:
        f.write(bad_configuration)

    with pytest.raises(pypim.InvalidConfigurationError) as exc:
        pypim.Client._from_configuration(config_path)

    assert message_content in str(exc)


def test_list_instance_error(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
):
    # Arrange
    # A server serving a 500 on ListInstance and ListDefinitions
    def server():
        _, update_request, rpc = testing_channel.take_unary_unary(LIST_INSTANCES_METHOD)
        rpc.terminate(None, [], StatusCode.INTERNAL, "I'm a teapot.")
        _, update_request, rpc = testing_channel.take_unary_unary(LIST_DEFINITIONS_METHOD)
        rpc.terminate(None, [], StatusCode.INTERNAL, "I'm a teapot.")
        return update_request

    testing_pool.submit(server)
    client = pypim.Client(testing_channel)

    # Act
    # List the instances and the definitions
    with pytest.raises(pypim.RemoteError) as exc1:
        client.list_instances()
    with pytest.raises(pypim.RemoteError) as exc2:
        client.list_definitions()

    # Assert
    # The user got the server message
    assert "I'm a teapot." in str(exc1)
    assert "I'm a teapot." in str(exc2)
    # And can inspect the inner error
    assert exc1.value.__cause__.code() == grpc.StatusCode.INTERNAL
    assert exc2.value.__cause__.code() == grpc.StatusCode.INTERNAL
