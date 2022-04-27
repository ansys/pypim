"""Client class module."""
import contextlib
import json
import logging
from typing import Sequence

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    GetInstanceRequest,
    ListDefinitionsRequest,
    ListInstancesRequest,
)
from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2_grpc import (
    ProductInstanceManagerStub,
)
import grpc

from ansys.platform.instancemanagement.definition import Definition
from ansys.platform.instancemanagement.exceptions import (
    InstanceNotFoundError,
    InvalidConfigurationError,
    RemoteError,
    UnsupportedProductError,
)
from ansys.platform.instancemanagement.instance import Instance
from ansys.platform.instancemanagement.interceptor import header_adder_interceptor

logger = logging.getLogger(__name__)


class Client(contextlib.AbstractContextManager):
    """Provides an high-level client object for interacting with the PIM API.

    This class exposes the methods of the PIM API.
    """

    _channel: grpc.Channel
    _stub: ProductInstanceManagerStub

    def __init__(self, channel: grpc.Channel) -> None:
        """Initialize the client library.

        Parameters
        ----------
        channel
            gRPC channel hosting the connection.

        Examples
        --------
            >>> import ansys.platform.instancemanagement as pypim
            >>> import grpc
            >>> channel = grpc.insecure_channel("127.0.0.0:50001")
            >>> client = pypim.Client(channel)

        """
        logger.info("Connecting.")
        self._channel = channel
        self._stub = ProductInstanceManagerStub(self._channel)

    def __exit__(self, *_):
        """Close the channel when used in a ``with`` statement."""
        self._channel.close()

    def close(self):
        """Close the connection.

        This method is called when using the client in a ``with`` statement.
        """
        self._channel.close()

    @staticmethod
    def _from_configuration(config_path: str):
        """Initialize the PyPIM client based on the configuration file.

        Parameters
        ----------
        config_path : str
            Path of the configuration file.

        Returns
        -------
        Client
            PyPIM client.

        Raises
        ------
        InvalidConfigurationError
            The configuration is not valid.
        """
        logger.debug("Initializing from %s", config_path)

        # Note: this configuration should likely become a full-featured object
        # to be shared across PyPIM class at some point.
        # The configuration is a plain json file with the settings to create the
        # grpc channel.

        with open(config_path, "r") as f:
            try:
                configuration = json.load(f)
            except json.JSONDecodeError:
                raise InvalidConfigurationError(config_path, "Invalid json.")

        # What follows should likely be done with a schema validation
        try:
            version = configuration["version"]
            if version != 1:
                raise InvalidConfigurationError(
                    config_path,
                    f'Unsupported version "{version}".\
Consider upgrading ansys-platform-instancemanagement.',
                )

            pim_configuration = configuration["pim"]
            tls = pim_configuration["tls"]
            if tls:
                raise InvalidConfigurationError(
                    config_path, f"Secured connection is not yet supported."
                )

            uri = pim_configuration["uri"]
            headers = [(key, value) for key, value in pim_configuration["headers"].items()]
        except KeyError as e:
            key = e.args[0]
            raise InvalidConfigurationError(
                config_path, f"The configuration is missing the entry {key}."
            )

        channel = grpc.intercept_channel(
            grpc.insecure_channel(uri), header_adder_interceptor(headers)
        )
        return Client(channel)

    def list_definitions(
        self,
        product_name: str = None,
        product_version: str = None,
        timeout: float = None,
    ) -> Sequence[Definition]:
        """Get the list of supported product definitions.

        Parameters
        ----------
        product_name : str, optional
            Filter by product name if provided. The default is ``None``.
        product_version : str, optional
            Filter by product version if provided. The default is ``None``.
        timeout : float, optional
            Set a timeout in seconds for the request if provided. The default
            is ``None``.

        Returns
        -------
        list
            List of supported product definitions.

        Examples
        --------
            >>> import ansys.platform.instancemanagement as pypim
            >>> client = pypim.connect()
            >>> for definition in client.list_definitions(product_name="mapdl"):
            >>>     print(f"MAPDL version {definition.version} is available on the server.")
                MAPDL version 221 is available on the server.

        """
        logger.debug(
            "Listing definitions for the product %s in version %s",
            product_name,
            product_version,
        )
        request = ListDefinitionsRequest(product_name=product_name, product_version=product_version)

        try:
            response = self._stub.ListDefinitions(request, timeout=timeout)
        except grpc.RpcError as exc:
            raise RemoteError(exc, exc.details()) from exc

        return [
            Definition._from_pim_v1(definition, self._stub) for definition in response.definitions
        ]

    def list_instances(self, timeout: float = None) -> Sequence[Instance]:
        """List the existing instances.

        Parameters
        ----------
        timeout : float, optional
            Maximum time in seconds for the request. The default is ``None``.

        Returns
        -------
        list
            List of instances.

        Examples
        --------
            >>> import ansys.platform.instancemanagement as pypim
            >>> client = pypim.connect()
            >>> for instance in client.list_instances():
            >>>     status = "ready" if instance.ready else "not ready"
            >>>     print(f"The instance {instance.name} is {status}.")
                The instance instances/mapdl-221-yAVne0ve is ready
        """
        logger.debug("Listing instances.")
        request = ListInstancesRequest()

        try:
            response = self._stub.ListInstances(request, timeout=timeout)
        except grpc.RpcError as exc:
            raise RemoteError(exc, exc.details()) from exc

        return [Instance._from_pim_v1(instance, self._stub) for instance in response.instances]

    def create_instance(
        self,
        product_name: str,
        product_version: str = None,
        requests_timeout: float = None,
    ) -> Instance:
        """Create a remote instance of a product based on its name and optionally its version.

        This effectively starts the product in the backend, according to the backend configuration.

        The created instance will not yet be ready to use. You must call
        :func:`~Instance.wait_for_ready()` to wait for the instance to be ready.

        Parameters
        ----------
        product_name : str
            Name of the product to start (for example, ``mapdl``).
        product_version : str, optional
            Version of the product (for example, ``"222"``). The default is ``None``.
        requests_timeout : float, optional
            Maximum time for each request in seconds. The default is ``None``.

        Returns
        -------
        Instance
            Instance of the product.

        Raises
        ------
        UnsupportedProductError
            The product or the selected version is not available remotely.

        Examples
        --------
            >>> import ansys.platform.instancemanagement as pypim
            >>> client = pypim.connect()
            >>> instance = client.create_instance(product_name="mapdl")
            >>> instance.wait_for_ready()
            >>> print(instance.services)
            >>> instance.delete()
                {'grpc': Service(uri='dns:10.240.4.231:50052', headers={})}

        """
        logger.debug(
            "Creating a product instance for %s in version %s.", product_name, product_version
        )
        definitions = self.list_definitions(
            product_name=product_name, product_version=product_version, timeout=requests_timeout
        )

        if len(definitions) == 0:
            raise UnsupportedProductError(
                product_name=product_name, product_version=product_version
            )
        definition = definitions[0]
        return definition.create_instance(timeout=requests_timeout)

    def get_instance(self, name: str, timeout: float = None) -> Instance:
        """Get a remote product instance by name.

        Parameters
        ----------
        name: str
            Name of the instance to get (for example, ``instances/mapdl-1212``).

        timeout : float, optional
            Maximum time in seconds for the request. The default is ``None``.

        Returns
        -------
        Instance
            A remote instance.

        Raises
        ------
            InstanceNotFoundError
                The instance does not exist.
        """
        logger.debug("Getting the instance %s.", name)
        request = GetInstanceRequest(name=name)

        try:
            instance = self._stub.GetInstance(request, timeout=timeout)
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.NOT_FOUND:
                raise InstanceNotFoundError(exc, f"The instance {name} does not exist.") from exc
            raise RemoteError(exc, exc.details()) from exc

        return Instance._from_pim_v1(instance, self._stub)
