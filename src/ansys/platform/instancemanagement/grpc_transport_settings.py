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

"""Grpc transport mode module."""
from enum import Enum, auto
from pathlib import Path

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    MtlsSettings,
    TransportMode,
    TransportSettings,
    UdsSettings,
)
from ansys.tools.common.cyberchannel import CertificateFiles


class GrpcTransportMode(Enum):
    """Enum containing the different modes of connection."""

    UNSPECIFIED = auto()
    INSECURE = auto()
    UDS = auto()
    MTLS = auto()
    WNUA = auto()


class GrpcTransportSettings:
    """Class containing the settings for the gRPC transport mode."""

    def __init__(
        self,
        mode: GrpcTransportMode = GrpcTransportMode.UNSPECIFIED,
        # uds_service: str | None = None,
        uds_dir: str | Path | None = None,
        uds_id: str | None = None,
        # uds_fullpath: str | Path | None = None,
        certs_dir: str | Path | None = None,
        server_cert_files: CertificateFiles | None = None,
        client_cert_files: CertificateFiles | None = None,
        grpc_options: list[tuple[str, object]] | None = None,
    ):
        """Initialize the gRPC transport mode settings.

        Parameters
        ----------
        mode : GrpcTransportMode
            The transport mode to use.
        uds_service : str, optional
            The name of the service to connect to when using UDS transport mode.
        uds_dir : str or Path, optional
            The directory where the UDS socket is located when using UDS transport mode.
        uds_id : str, optional
            The ID of the UDS socket to connect to when using UDS transport mode.
        uds_fullpath : str or Path, optional
            The full path to the UDS socket to connect to when using UDS transport mode.
        certs_dir : str or Path, optional
            The directory where the certificates are located when using mTLS transport mode.
        server_cert_files : CertificateFiles, optional
            The server certificate files to use when using mTLS transport mode.
        client_cert_files : CertificateFiles, optional
            The client certificate files to use when using mTLS transport mode.
        grpc_options : list of tuple of (str, object), optional
            The gRPC channel options to use when creating the gRPC channel.
            Each option is a tuple containing the option name and its value.
        """
        self.mode = mode
        # self.uds_service = uds_service
        self.uds_dir = uds_dir
        self.uds_id = uds_id
        # self.uds_fullpath = uds_fullpath
        self.certs_dir = certs_dir
        self.server_cert_files = server_cert_files
        self.client_cert_files = client_cert_files
        self.grpc_options = grpc_options

    def to_transport_settings(self) -> TransportSettings:
        """Convert to TransportSettings."""
        match self.mode:
            case GrpcTransportMode.MTLS:
                ca_cert_path = ""
                if self.server_cert_files is not None and self.client_cert_files is not None:
                    if self.server_cert_files.ca_file != self.client_cert_files.ca_file:
                        raise ValueError(
                            "Server and client certificate files must have the same CA file."
                        )
                    ca_cert_path = str(self.server_cert_files.ca_file)
                server_cert_path = ""
                server_key_path = ""
                client_cert_path = ""
                client_key_path = ""
                if self.server_cert_files is not None:
                    if self.server_cert_files.cert_file is not None:
                        server_cert_path = str(self.server_cert_files.cert_file)
                    if self.server_cert_files.key_file is not None:
                        server_key_path = str(self.server_cert_files.key_file)
                if self.client_cert_files is not None:
                    if self.client_cert_files.cert_file is not None:
                        client_cert_path = str(self.client_cert_files.cert_file)
                    if self.client_cert_files.key_file is not None:
                        client_key_path = str(self.client_cert_files.key_file)
                return TransportSettings(
                    mode=TransportMode.TRANSPORT_MODE_MTLS,
                    mtls_settings=MtlsSettings(
                        cert_folder_path=str(self.certs_dir) if self.certs_dir else "",
                        server_cert_path=server_cert_path,
                        server_key_path=server_key_path,
                        ca_cert_path=ca_cert_path,
                        client_cert_path=client_cert_path,
                        client_key_path=client_key_path,
                    ),
                )
            case GrpcTransportMode.UDS:
                return TransportSettings(
                    mode=TransportMode.TRANSPORT_MODE_UDS,
                    uds_settings=UdsSettings(
                        socket_folder_path=str(self.uds_dir) if self.uds_dir else "",
                        id=self.uds_id if self.uds_id else "",
                    ),
                )
            case GrpcTransportMode.INSECURE:
                return TransportSettings(mode=TransportMode.TRANSPORT_MODE_INSECURE)
            case GrpcTransportMode.WNUA:
                return TransportSettings(mode=TransportMode.TRANSPORT_MODE_WNUA)
            case _:
                return TransportSettings(mode=TransportMode.TRANSPORT_MODE_UNSPECIFIED)
