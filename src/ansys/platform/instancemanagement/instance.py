"""Instance class module."""


import contextlib
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
import grpc

from ansys.platform.instancemanagement.exceptions import (
    InstanceNotFoundError,
    InstanceNotReadyError,
    RemoteError,
    UnsupportedServiceError,
)
from ansys.platform.instancemanagement.service import Service

logger = logging.getLogger(__name__)


@dataclass
class Instance(contextlib.AbstractContextManager):
    """Provides a remote instance of a product.

    This class is a context manager and can be used with the ``with`` statement to
    automatically stop the remote instance when the tasks are finished.
    """

    definition_name: str
    """Name of the definition that created this instance."""

    name: str
    """Name of the instance.

    This name is chosen by the server and always start with ``"instances/"``."""

    ready: bool
    """Whether the instance is ready.

    If ``True``, the ``services`` field contains the list of entry points
    exposed by the instance.

    If ``False``, the ``status_message`` field contains a human-readable
    reason."""

    status_message: str
    """Status of the instance.

    Human-readable message describing the status of the instance.
    This field is always filled when the instance is not ready."""

    services: Mapping[str, Service]
    """List of entry points exposed by the instance.

    This field is only filled when the instance is ready.
    If the instance exposes a gRPC API, it is named ``grpc``.
    If the instance exposes a REST-like API, it is named ``http``.

    It may contain additional entries for custom scenarios such as sidecar services
    or other protocols."""

    _stub: ProductInstanceManagerStub = field(default=None, compare=False)

    def __post_init__(self):
        """Initialize non dataclass members.

        ``dataclass`` construction
        """
        if self.status_message:
            # TODO: instance specific logger
            logger.info(self.status_message)

    def __exit__(self, *_):
        """Delete the instance when used in a ``with`` statement."""
        self.delete()

    @staticmethod
    def _create(definition_name: str, stub: ProductInstanceManagerStub, timeout: float = None):
        """Create a product instance from the given definition.

        Parameters
        ----------
        timeout : float
            Time in seconds to create the instance. The default is ``None``.

        Returns
        -------
        Instance
            Product instance.
        """
        request = CreateInstanceRequest(instance=InstanceV1(definition_name=definition_name))
        instance = stub.CreateInstance(request, timeout=timeout)
        return Instance._from_pim_v1(instance, stub)

    def delete(self, timeout: float = None):
        """Delete the remote product instance.

        Parameters
        ----------
        timeout : float, optional
            Time in seconds to delete the instance. The default is ``None``.
        """
        request = DeleteInstanceRequest(name=self.name)
        self._stub.DeleteInstance(request, timeout=timeout)

    def update(self, timeout: float = None):
        """Update the instance information from the remote status.

        Parameters
        ----------
        timeout : float, optional
            Time in seconds to update the instance. The default is ``None``.

        Raises
        ------
        InstanceNotFoundError
            The instance was deleted.

        RemoteError
            Unexpected server error.
        """
        request = GetInstanceRequest(name=self.name)

        try:
            instance = self._stub.GetInstance(request, timeout=timeout)
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.NOT_FOUND:
                raise InstanceNotFoundError(exc, f"The instance {self.name} was deleted.") from exc
            raise RemoteError(exc, exc.details()) from exc

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

        Parameters
        ----------
        polling_interval : float, optional
            Time to wait between each request in seconds. The default is ``0.5``.
        timeout_per_request : float, optional
            Timeout for each request in seconds. The default is ``None``.

        Raises
        ------
        InstanceNotFoundError
            The instance was deleted.

        RemoteError
            Unexpected server error.
        """
        self.update(timeout=timeout_per_request)
        while not self.ready:
            time.sleep(polling_interval)
            self.update(timeout=timeout_per_request)

    def build_grpc_channel(self, service_name: str = "grpc", **kwargs):
        """Build a gRPC channel to communicate with this instance.

        The instance must be ready before calling this method.

        Parameters
        ----------
        service_name : str, optional
            Custom service name. The default is ``"grpc"``.
        kwargs: list
            Named argument to pass to the gRPC channel creation.

        Returns
        -------
        grpc.Channel
            gRPC channel preconfigured to work with the instance.

        Raises
        ------
        InstanceNotReadyError
            The instance is not yet ready.

        UnsupportedServiceError
            The instance does not support the service.

        Examples
        --------
            >>> import ansys.platform.instancemanagement as pypim
            >>> from ansys.mapdl.core import Mapdl
            >>> pim=pypim.connect()
            >>> instance = pim.create_instance(product_name="mapdl", product_version="221")
            >>> instance.wait_for_ready()
            >>> channel = instance.build_grpc_channel(
            >>>     options=[("grpc.max_receive_message_length", 8*1024**2)]
            >>> )
            >>> mapdl = Mapdl(channel=channel)
            >>> print(mapdl)
            >>> instance.delete()
                Product:             Ansys Mechanical Enterprise
                MAPDL Version:       22.1
                ansys.mapdl Version: 0.61.2
        """
        if not self.ready:
            raise InstanceNotReadyError(self.name)

        service = self.services.get(service_name, None)
        if not service:
            raise UnsupportedServiceError(self.name, service_name)

        return service._build_grpc_channel(**kwargs)

    @staticmethod
    def _from_pim_v1(instance: InstanceV1, stub: ProductInstanceManagerStub = None):
        """Create a PyPIM instance from the raw protobuf message.

        Parameters
        ----------
        instance : InstanceV1
            Raw protobuf message from the PIM API.
        stub : ProductInstanceManagerStub, optional
            PIM stub.
        """
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
