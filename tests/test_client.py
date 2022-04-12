from concurrent.futures import ThreadPoolExecutor
import os
from unittest.mock import MagicMock, patch

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    Definition as DefinitionV1,
)
from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    ListDefinitionsRequest,
    ListDefinitionsResponse,
)
import ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2_grpc as product_instance_manager_pb2_grpc  # noqa: E501
import grpc
from grpc import StatusCode
import grpc_testing
import pytest

import ansys.platform.instancemanagement as pypim
from ansys.platform.instancemanagement import Client, Definition, Instance
from conftest import LIST_DEFINITIONS_METHOD


@pytest.mark.parametrize(
    ("arguments", "expected_request"),
    [
        (
            {},
            ListDefinitionsRequest(),
        ),
        (
            {"product_name": "my-product"},
            ListDefinitionsRequest(product_name="my-product"),
        ),
        (
            {"product_version": "221"},
            ListDefinitionsRequest(product_version="221"),
        ),
        (
            {"product_name": "my-product", "product_version": "221"},
            ListDefinitionsRequest(product_name="my-product", product_version="221"),
        ),
    ],
)
def test_definitions_request(
    testing_pool: ThreadPoolExecutor,
    testing_channel: grpc_testing.Channel,
    arguments,
    expected_request,
):
    def client():
        client = Client(testing_channel)
        return client.definitions(**arguments, timeout=1)

    def server():
        _, request, rpc = testing_channel.take_unary_unary(LIST_DEFINITIONS_METHOD)
        rpc.terminate(ListDefinitionsResponse(), [], StatusCode.OK, "")
        return request

    client_future = testing_pool.submit(client)
    server_future = testing_pool.submit(server)

    assert client_future.result() == []
    assert server_future.result() == expected_request


@pytest.mark.parametrize(
    ("response", "expected_definitions"),
    [
        (
            ListDefinitionsResponse(),
            [],
        ),
        (
            ListDefinitionsResponse(
                definitions=[
                    DefinitionV1(
                        name="definitions/my-definition",
                        product_name="my-product",
                        product_version="221",
                        available_service_names=["grpc", "sidecar"],
                    ),
                    DefinitionV1(
                        name="definitions/my-other-definition",
                        product_name="my-product",
                        product_version="222",
                        available_service_names=["http"],
                    ),
                ]
            ),
            [
                Definition(
                    name="definitions/my-definition",
                    product_name="my-product",
                    product_version="221",
                    available_service_names=["grpc", "sidecar"],
                ),
                Definition(
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
    def client():
        client = Client(testing_channel)
        return client.definitions(timeout=1)

    def server():
        _, _, rpc = testing_channel.take_unary_unary(LIST_DEFINITIONS_METHOD)
        rpc.terminate(response, [], StatusCode.OK, "")

    client_future = testing_pool.submit(client)
    server_future = testing_pool.submit(server)

    server_future.result()
    assert client_future.result() == expected_definitions


def test_create_instance(testing_channel):
    # Arrange
    # A client with two definitions
    client = Client(testing_channel)
    definitions = [
        Definition(
            name="definitions/the-good-one",
            product_name="calculator",
            product_version="221",
            available_service_names=["fax"],
        ),
        Definition(
            name="definitions/the-bad-one",
            product_name="calculator",
            product_version="195",
            available_service_names=["fax"],
        ),
    ]
    instance = Instance(
        definition_name="definitions/the-good-one",
        name="instances/calculator-42",
        ready=False,
        status_message="loading...",
        services={},
    )
    definitions[0].create_instance = MagicMock(return_value=instance)
    definitions[1].create_instance = MagicMock()
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
    # A basic implementation of PIM
    received_metadata = []

    class PIMServicer(product_instance_manager_pb2_grpc.ProductInstanceManagerServicer):
        def ListDefinitions(self, _, context):
            received_metadata.append(context.invocation_metadata())
            return ListDefinitionsResponse()

    server = grpc.server(testing_pool)
    product_instance_manager_pb2_grpc.add_ProductInstanceManagerServicer_to_server(
        PIMServicer(), server
    )

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
        client = pypim.connect()
        client.definitions(product_name="hello-world", product_version="231")

    # Assert
    # The server got the request with the intended headers
    assert len(received_metadata) == 1
    received_metadata_dict = dict(received_metadata[0])
    assert received_metadata_dict["token"] == "007"
    assert received_metadata_dict["identity"] == "james bond"
