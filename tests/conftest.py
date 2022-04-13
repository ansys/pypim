from concurrent.futures import ThreadPoolExecutor

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import DESCRIPTOR
import grpc_testing
import pytest

PIM_SERVICE = DESCRIPTOR.services_by_name["ProductInstanceManager"]
LIST_DEFINITIONS_METHOD = PIM_SERVICE.methods_by_name["ListDefinitions"]
CREATE_INSTANCE_METHOD = PIM_SERVICE.methods_by_name["CreateInstance"]
DELETE_INSTANCE_METHOD = PIM_SERVICE.methods_by_name["DeleteInstance"]
GET_INSTANCE_METHOD = PIM_SERVICE.methods_by_name["GetInstance"]
LIST_INSTANCES_METHOD = PIM_SERVICE.methods_by_name["ListInstances"]


@pytest.fixture()
def testing_pool():
    """A thread pool with two workers (client and server)."""
    pool = ThreadPoolExecutor(max_workers=2)
    yield pool
    pool.shutdown(wait=False)


@pytest.fixture()
def testing_channel():
    """A gRPC channel for use in tests."""
    channel = grpc_testing.channel(
        DESCRIPTOR.services_by_name.values(),
        grpc_testing.strict_real_time(),
    )
    yield channel
