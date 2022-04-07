from concurrent.futures import ThreadPoolExecutor

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    Definition as DefinitionV1,
)
from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    ListDefinitionsRequest,
    ListDefinitionsResponse,
)
from grpc import StatusCode
import grpc_testing
import pytest

from ansys.platform.instancemanagement import Client, Definition
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

    assert client_future.result() == {}
    assert server_future.result() == expected_request


@pytest.mark.parametrize(
    ("response", "expected_definitions"),
    [
        (
            ListDefinitionsResponse(),
            {},
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
            {
                "definitions/my-definition": Definition(
                    name="definitions/my-definition",
                    product_name="my-product",
                    product_version="221",
                    available_service_names=["grpc", "sidecar"],
                ),
                "definitions/my-other-definition": Definition(
                    name="definitions/my-other-definition",
                    product_name="my-product",
                    product_version="222",
                    available_service_names=["http"],
                ),
            },
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
