"""Instance class module."""

from dataclasses import dataclass, field
import logging
import time
from typing import Mapping

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    CreateInstanceRequest,
    DeleteInstanceRequest,
    GetInstanceRequest,
)
from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    Instance as InstanceV1,
)
from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2_grpc import (
    ProductInstanceManagerStub,
)

from ansys.platform.instancemanagement.service import Service

logger = logging.getLogger(__name__)


@dataclass
class Instance:
    """A remote instance of a product."""

    definition_name: str
    """Name of the definition that created this instance."""

    name: str
    """Name of the instance.

    This name is chosen by the server and always start with "instances/"."""

    ready: bool
    """Indicates if the instance is ready.

    If `True` then the ``services`` field will contain the list of entrypoints
    exposed by the instance.

    If `False` then the ``status_message`` field will
    contain a human readable reason."""

    status_message: str
    """Status of the instance.

    Human readable message describing the status of the instance.
    This field is always filled when the instance is not ready."""

    services: Mapping[str, Service]
    """List of entrypoints exposed by the instance.

    This field is only filled when the instance is ready.
    If the instance exposes a gRPC API, it will be named `grpc`.
    If the instance exposes a REST-like API, it will be named `http`.

    It may contain additional entries for custom scenarios such as sidecar services
    or other protocols."""

    _stub: ProductInstanceManagerStub = field(default=None, compare=False)

    def __post_init__(self):
        """Initialize non dataclass members.

        `dataclass` construction
        """
        if self.status_message:
            # TODO: instance specific logger
            logger.info(self.status_message)

    @staticmethod
    def _create(definition_name: str, stub: ProductInstanceManagerStub, timeout: float = None):
        """Create a product instance from the given definition.

        Args:
            timeout (float): Time (in seconds) to create the instance.

        Returns:
            Instance: The product instance
        """
        request = CreateInstanceRequest(instance=InstanceV1(definition_name=definition_name))
        instance = stub.CreateInstance(request, timeout=timeout)
        return Instance._from_pim_v1(instance, stub)

    def delete(self, timeout: float = None):
        """Delete the remote product instance.

        Args:
            timeout (float, optional): Time (in seconds) to delete the instance. Defaults to None.
        """
        request = DeleteInstanceRequest(name=self.name)
        self._stub.DeleteInstance(request, timeout=timeout)

    def update(self, timeout: float = None):
        """Update the instance information from the remote status.

        Args:
            timeout (float, optional): Time (in seconds) to update the instance. Defaults to None.
        """
        request = GetInstanceRequest(name=self.name)
        instance = self._stub.GetInstance(request, timeout=timeout)
        self.name = instance.name
        self.definition_name = instance.definition_name

        if instance.status_message and self.status_message != instance.status_message:
            # This should be done through property, but this does not play well with dataclasses
            # TODO: instance logger
            logger.info(instance.status_message)

        self.status_message = instance.status_message
        self.services = {
            name: Service._from_pim_v1(value) for name, value in instance.services.items()
        }
        self.ready = instance.ready

    def wait_for_ready(self, polling_interval: float = 0.5, timeout_per_request: float = None):
        """Wait for the instance to be ready.

        After calling this method, the instance services are filled and ready to
        be used.

        Args:
            polling_interval (float, optional): Time to wait between each
            request in seconds. Defaults to 0.5.
            timeout_per_request (float, optional): Timeout for each request in seconds.
            Defaults to None.
        """
        self.update(timeout=timeout_per_request)
        while not self.ready:
            time.sleep(polling_interval)
            self.update(timeout=timeout_per_request)

    def build_grpc_service(self, service_name: str = "grpc", **kwargs):
        """Build a gRPC channel to communicate with this instance.

        The instance must be ready before calling this method.

        Args:
            service_name (str, optional): Custom service name. Defaults to "grpc".
            kwargs: Will be passed to the grpc channel creation.

        Raises:
            ValueError: The instance does not support gRPC, or the service name is wrong.

        Returns:
            grpc.Channel: gRPC channel preconfigured to work with the instance.
        """
        if not self.ready:
            raise RuntimeError(f"The instance is not ready.")

        service = self.services.get(service_name, None)
        if not service:
            raise ValueError(f"There is no {service_name} service in the remote instance.")

        return service._build_grpc_channel(**kwargs)

    @staticmethod
    def _from_pim_v1(instance: InstanceV1, stub: ProductInstanceManagerStub = None):
        """Create a PyPIM instance from the raw protobuf message.

        Args:
            instance (InstanceV1): The raw protobuf message from the PIM API.
            stub (ProductInstanceManagerStub, optional): PIM Stub
        """
        if instance.name and not instance.name.startswith("instances/"):
            raise ValueError("An instance name must start with `instances/`")

        if not instance.definition_name or not instance.definition_name.startswith("definitions/"):
            raise ValueError(
                "An instance must have a definition name that starts with definitions/"
            )

        return Instance(
            name=instance.name,
            definition_name=instance.definition_name,
            status_message=instance.status_message,
            services={
                name: Service._from_pim_v1(value) for name, value in instance.services.items()
            },
            ready=instance.ready,
            _stub=stub,
        )
