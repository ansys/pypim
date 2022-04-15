from concurrent.futures import ThreadPoolExecutor
import os
from unittest.mock import MagicMock, patch

from ansys.api.platform.instancemanagement.v1 import product_instance_manager_pb2 as pb2
from ansys.api.platform.instancemanagement.v1 import product_instance_manager_pb2_grpc as pb2_grpc
import grpc
from grpc import StatusCode
import grpc_testing
import pytest

import ansys.platform.instancemanagement as pypim
from conftest import LIST_DEFINITIONS_METHOD, LIST_INSTANCES_METHOD


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
    client.definitions(**arguments, timeout=1)

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
    definitions = client.definitions(timeout=1)
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
    client.instances(timeout=1)

    # Assert
    # The client sent an empty ListInstanceRequest
    assert server_future.result() == pb2.ListInstancesRequest()


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
    instances = client.instances(timeout=1)

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
    object.__setattr__(definitions[0], "create_instance", MagicMock(return_value=instance))
    object.__setattr__(definitions[1], "create_instance", MagicMock())
    client.definitions = MagicMock(return_value=definitions)

    # Act
    created_instance = client.create_instance(
        product_name="definitions/the-good-one", requests_timeout=0.32
    )

    # Assert
    # The method created an instance from the first definition
    client.definitions.assert_called_once_with(
        product_name="definitions/the-good-one", product_version=None, timeout=0.32
    )
    definitions[0].create_instance.assert_called_once_with(timeout=0.32)
    definitions[1].create_instance.assert_not_called()
    assert created_instance == instance


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
            client.definitions(product_name="hello-world", product_version="231")

    # Assert
    # The server got the request with the intended headers
    assert len(received_metadata) == 1
    received_metadata_dict = dict(received_metadata[0])
    assert received_metadata_dict["token"] == "007"
    assert received_metadata_dict["identity"] == "james bond"
