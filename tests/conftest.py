# Copyright (C) 2022 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

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
