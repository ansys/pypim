"""Exceptions raised by PyPIM."""


import grpc


class NotConfiguredError(RuntimeError):
    """Indicates an attempt was made to use PyPIM without the mandatory configuration.

    Consider calling :func:`~is_configured()` before using :func:`~connect()`.
    """

    pass


class InstanceNotReadyError(RuntimeError):
    """Indicates an attempt was made to communicate with an instance that is not yet ready.

    Consider calling :func:`~Instance.wait_for_ready`
    or checking :attr:`~Instance.ready` before use.
    """

    instance_name: str
    """Name of the instance."""

    def __init__(self, instance_name: str) -> None:
        """Construct the error from the instance name."""
        self.instance_name = instance_name

        super().__init__(f"{instance_name} is not ready")


class UnsupportedServiceError(ValueError):
    """Indicates an attempt was made to communicate with an instance using a service that is not\
        supported."""

    instance_name: str
    """Name of the instance."""

    service_name: str
    """Name of the unsupported service."""

    def __init__(self, instance_name: str, service_name: str) -> None:
        """Construct the error from the instance name and unsupported service."""
        self.instance_name = instance_name
        self.service_name = service_name

        super().__init__(f'{instance_name} does not support the service "{service_name}"')


class InvalidConfigurationError(RuntimeError):
    """Indicates PyPIM is configured, but the configuration is invalid."""

    configuration_path: str
    """Path of the invalid configuration."""

    def __init__(self, configuration_path: str, message: str) -> None:
        """Construct the error from the configuration path and issue."""
        self.configuration_path = configuration_path

        super().__init__(f"{configuration_path} is invalid: {message}")


class UnsupportedProductError(RuntimeError):
    """Indicates that the product or version is not supported by the remote server.

    This error is raised when trying to start a product that does not contain
    any matching definition in the remote server.

    You can try to lift some of the constraints, such as the version constraint.
    """

    product_name: str
    """Name of the requested product."""

    product_version: str
    """Version of the requested product."""

    def __init__(self, product_name: str, product_version: str) -> None:
        """Construct the error from the unsupported product, version, or both."""
        self.product_name = product_name
        self.product_version = product_version
        if product_version:
            super().__init__(
                f"The remote server does not support {self.product_name} in version"
                f" {self.product_version}."
            )
        else:
            super().__init__(f"The remote server does not support {self.product_name}.")


# TODO: We should likely have more specialized versions, but for now
# let's focus on improving the messages coming from the remote
class RemoteError(RuntimeError):
    """Indicates a remote request failed.

    When this error is raised, the `__cause__` member contains the original :class:~`grpc.Call`.
    """

    call: grpc.Call
    """Failed gRPC call."""

    def __init__(self, call: grpc.Call, *args) -> None:
        """Construct the error from the grpc exception."""
        self.call = call
        super().__init__(*args)


class InstanceNotFoundError(RemoteError):
    """Indicates that the instance does not exist or was removed."""

    pass
