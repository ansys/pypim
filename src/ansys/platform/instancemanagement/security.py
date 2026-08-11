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

"""Public, protobuf-free security settings for instance creation."""

from dataclasses import dataclass
from typing import Dict, Union

from google.protobuf.empty_pb2 import Empty

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    InstanceSecuritySettings,
    MtlsCertificatePaths as MtlsCertificatePathsV1,
    MtlsSettings as MtlsSettingsV1,
    UdsSettings as UdsSettingsV1,
)


@dataclass(frozen=True)
class InsecureSettings:
    """Insecure gRPC channel (no TLS)."""

    def _to_pim_v1(self) -> InstanceSecuritySettings:
        """Convert to the PIM API v1 protobuf message."""
        return InstanceSecuritySettings(insecure=Empty())


@dataclass(frozen=True)
class WnuaSettings:
    """Windows user-based authentication (Windows only)."""

    def _to_pim_v1(self) -> InstanceSecuritySettings:
        """Convert to the PIM API v1 protobuf message."""
        return InstanceSecuritySettings(wnua=Empty())


@dataclass(frozen=True)
class MtlsCertificatePaths:
    """Individual certificate and key file paths for mTLS."""

    server_key_path: str
    server_certificate_path: str
    ca_certificate_path: str
    client_key_path: str
    client_certificate_path: str


@dataclass(frozen=True)
class MtlsSettings:
    """Mutual TLS settings.

    Provide certificates either as a directory (``certificates_directory``)
    or as individual file paths (``certificate_paths``), but not both. If
    neither is set, the server falls back to its own default resolution.
    """

    certificates_directory: Union[str, None] = None
    certificate_paths: Union[MtlsCertificatePaths, None] = None

    def __post_init__(self) -> None:
        """Validate that at most one certificate source is set."""
        if self.certificates_directory is not None and self.certificate_paths is not None:
            raise ValueError(
                "Provide either 'certificates_directory' or 'certificate_paths', not both."
            )

    def _to_pim_v1(self) -> InstanceSecuritySettings:
        """Convert to the PIM API v1 protobuf message."""
        if self.certificate_paths is not None:
            paths = self.certificate_paths
            mtls = MtlsSettingsV1(
                certificate_paths=MtlsCertificatePathsV1(
                    server_key_path=paths.server_key_path,
                    server_certificate_path=paths.server_certificate_path,
                    ca_certificate_path=paths.ca_certificate_path,
                    client_key_path=paths.client_key_path,
                    client_certificate_path=paths.client_certificate_path,
                )
            )
        elif self.certificates_directory is not None:
            mtls = MtlsSettingsV1(certificates_directory=self.certificates_directory)
        else:
            mtls = MtlsSettingsV1()
        return InstanceSecuritySettings(mtls=mtls)


@dataclass(frozen=True)
class UdsSettings:
    """Unix Domain Socket connection settings.

    Provide either a full ``socket_path`` or the ``socket_directory`` /
    ``socket_identifier`` pair, but not both.  If neither is set, the server
    falls back to its own default resolution.
    """

    socket_path: Union[str, None] = None
    socket_directory: Union[str, None] = None
    socket_identifier: Union[str, None] = None

    def __post_init__(self) -> None:
        """Validate that 'socket_path' is not combined with directory/identifier."""
        if self.socket_path is not None and (
            self.socket_directory is not None or self.socket_identifier is not None
        ):
            raise ValueError(
                "'socket_path' cannot be combined with 'socket_directory' or 'socket_identifier'."
            )

    def _to_pim_v1(self) -> InstanceSecuritySettings:
        """Convert to the PIM API v1 protobuf message."""
        properties: Dict[str, str] = {}
        if self.socket_path is not None:
            properties["socket_path"] = self.socket_path
        else:
            if self.socket_directory is not None:
                properties["socket_directory"] = self.socket_directory
            if self.socket_identifier is not None:
                properties["socket_identifier"] = self.socket_identifier

        return InstanceSecuritySettings(uds=UdsSettingsV1(**properties))


SecuritySettings = Union[InsecureSettings, MtlsSettings, WnuaSettings, UdsSettings]
