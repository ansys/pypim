from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    Service as ServiceV1,
)
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
