from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    Definition as DefinitionV1,
)
import pytest

from ansys.platform.instancemanagement import Definition


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
    ],
)
def test_from_pim_v1_proto_value_error(invalid_definition):
    with pytest.raises(ValueError):
        Definition._from_pim_v1(invalid_definition)
