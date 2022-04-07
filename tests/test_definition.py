from unittest.mock import patch

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    Definition as DefinitionV1,
)
from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2_grpc import (
    ProductInstanceManagerStub,
)
import pytest

from ansys.platform.instancemanagement import Definition
from ansys.platform.instancemanagement.instance import Instance


def test_from_pim_v1_proto():
    definition = Definition._from_pim_v1(
        DefinitionV1(
            name="definitions/my_def",
            product_name="my_product",
            product_version="221",
            available_service_names=["grpc", "http"],
        )
    )

    assert definition.name == "definitions/my_def"
    assert definition.product_name == "my_product"
    assert definition.product_version == "221"
    assert sorted(definition.available_service_names) == sorted(["grpc", "http"])


@pytest.mark.parametrize(
    "invalid_definition",
    [
        DefinitionV1(
            name="invalid",
            product_name="my_product",
            product_version="221",
            available_service_names=["grpc", "http"],
        ),
        DefinitionV1(
            name="definitions/my_def",
            product_name="my_product",
            product_version="",
            available_service_names=["grpc", "http"],
        ),
        DefinitionV1(
            name="definitions/my_def",
            product_name="my_product",
            product_version="221",
            available_service_names=[],
        ),
        DefinitionV1(
            name="definitions/my_def",
            product_name="",
            product_version="221",
            available_service_names=[],
        ),
    ],
)
def test_from_pim_v1_proto_value_error(invalid_definition):
    with pytest.raises(ValueError):
        Definition._from_pim_v1(invalid_definition)


def test_create_instance(testing_channel):
    stub = ProductInstanceManagerStub(testing_channel)
    definition = Definition(
        name="definitions/my_def",
        product_name="my_product",
        product_version="221",
        available_service_names=["grpc", "http"],
        _stub=stub,
    )
    with patch.object(
        Instance,
        "_create",
        return_value=Instance(
            definition_name="definitions/my_def",
            name="instances/something-123",
            ready=False,
            status_message="loading...",
            services={},
        ),
    ) as mock_instance_create:
        definition.create_instance(0.1)
    mock_instance_create.assert_called_once_with(
        definition_name="definitions/my_def", timeout=0.1, stub=stub
    )
