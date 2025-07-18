# Copyright (C) 2022 - 2025 ANSYS, Inc. and/or its affiliates.
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

"""Definition class module."""

from typing import Sequence

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    Definition as DefinitionV1,
)
from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2_grpc import (
    ProductInstanceManagerStub,
)

from ansys.platform.instancemanagement.configuration import Configuration
from ansys.platform.instancemanagement.instance import Instance


class Definition:
    """Provides a definition of a product that can be started using the PIM API.

    The definition is a static object describing a product that can be started remotely.
    """

    _name: str
    _product_name: str
    _product_version: str
    _available_service_names: Sequence[str]
    _stub: ProductInstanceManagerStub = None

    @property
    def name(self) -> str:
        """Name of the definition.

        This name is assigned by the server and always starts with ``"definitions/"``.
        This name is arbitrary. You should not rely on any static value.
        """
        return self._name

    @property
    def product_name(self) -> str:
        """Name of the product.

        This is the name of the product that can be started. For example, ``"mapdl"`` or
        ``"fluent"``.
        """
        return self._product_name

    @property
    def product_version(self) -> str:
        """Version of the product.

        This is a string describing the version.
        When the product is following the release process for the Ansys unified installation,
        the version is three digits, such as ``221``.
        """
        return self._product_version

    @property
    def available_service_names(self) -> Sequence[str]:
        """List of the available service names.

        If the product exposes a gRPC API, the service is named ``grpc``.
        If the product exposes a REST-like API, the service is named ``http``.
        Custom entries might also be listed, either for sidecar services or
        other protocols.
        """
        return self._available_service_names

    def __init__(
        self,
        name: str,
        product_name: str,
        product_version: str,
        available_service_names: Sequence[str],
        stub: ProductInstanceManagerStub = None,
    ):
        """Create a Definition."""
        self._name = name
        self._product_name = product_name
        self._product_version = product_version
        self._available_service_names = available_service_names
        self._stub = stub

    def __eq__(self, obj):
        """Test for equality."""
        if not isinstance(obj, Definition):
            return False
        return (
            self.name == obj.name
            and self.product_name == obj.product_name
            and self.product_version == obj.product_version
            and self.available_service_names == obj.available_service_names
        )

    def __repr__(self):
        """Python-callable description."""
        return (
            f"Definition(name={repr(self.name)}, product_name={repr(self.product_name)},"
            f" product_version={repr(self.product_version)}, available_service_names="
            f"{repr(self.available_service_names)})"
        )

    def create_instance(
        self, timeout: float = None, configuration: Configuration = None
    ) -> Instance:
        """Create a product instance from this definition.

        Parameters
        ----------
        timeout : float
            Time in seconds to create the instance. The default is ``None``.

        Returns
        -------
        instance
            Product instance.
        """
        return Instance._create(
            definition_name=self.name, stub=self._stub, timeout=timeout, configuration=configuration
        )

    @staticmethod
    def _from_pim_v1(definition: DefinitionV1, stub: ProductInstanceManagerStub = None):
        """Build a definition from the PIM API v1 protobuf object.

        Parameters
        ----------
        definition : DefinitionV1
            Raw PIM API v1 protobuf object.
        stub : ProductInstanceManagerStub
            Stub for the PIM instance. The default is ``None``.

        Returns
        -------
        Instance
            PyPIM instance definition.
        """
        return Definition(
            definition.name,
            definition.product_name,
            definition.product_version,
            definition.available_service_names,
            stub,
        )
