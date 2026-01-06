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

from unittest.mock import patch

from ansys.api.platform.instancemanagement.v1 import product_instance_manager_pb2 as pb2
from ansys.api.platform.instancemanagement.v1 import product_instance_manager_pb2_grpc as pb2_grpc

import ansys.platform.instancemanagement as pypim


def test_from_pim_v1_proto():
    definition = pypim.Definition._from_pim_v1(
        pb2.Definition(
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


def test_create_instance(testing_channel):
    # Arrange
    # A mocked Instance class and a definition
    with patch.object(
        pypim.Instance,
        "_create",
        return_value=pypim.Instance(
            definition_name="definitions/my_def",
            name="instances/something-123",
            ready=False,
            status_message="loading...",
            services={},
        ),
    ) as mock_instance_create:
        stub = pb2_grpc.ProductInstanceManagerStub(testing_channel)
        definition = pypim.Definition(
            name="definitions/my_def",
            product_name="my_product",
            product_version="221",
            available_service_names=["grpc", "http"],
            stub=stub,
        )

        configuration = pypim.Configuration(
            headers=[],
            tls=False,
            uri="dns:instancemanagement.example.com:443",
            access_token="Bearer 007",
        )
        # Act
        # Create the instance from the definition
        definition.create_instance(0.1, configuration)

    # Assert
    # The mocked Instance class was correctly called
    mock_instance_create.assert_called_once_with(
        definition_name="definitions/my_def", timeout=0.1, stub=stub, configuration=configuration
    )


def test_str():
    definition_str = str(
        pypim.Definition(
            name="definitions/my_def",
            product_name="my_product",
            product_version="221",
            available_service_names=["grpc"],
        )
    )
    assert "definitions/my_def" in definition_str
    assert "my_product" in definition_str
    assert "221" in definition_str
    assert "grpc" in definition_str


def test_repr():
    from ansys.platform.instancemanagement import Definition  # noqa

    definition = pypim.Definition(
        name="definitions/my_def",
        product_name="my_product",
        product_version="221",
        available_service_names=["grpc"],
    )

    assert definition == eval(repr(definition))
