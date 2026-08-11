.. _security:

########
Security
########

.. currentmodule:: ansys.platform.instancemanagement

PyPIM involves gRPC connections at two different points, and each can be
secured independently:

#. The connection from the PyPIM **client** to the **PIM server** itself,
   used for :func:`~Client.list_definitions`, :func:`~Client.create_instance`,
   and the other PIM API calls.
#. The connection from the PyPIM client to a **product instance** started by
   the PIM server. The transport used for this connection is decided by the
   PIM server and communicated back to the client through the created
   :class:`Instance`.

Both connections support the same set of transports:

* ``insecure``: no transport security. This is the default.
* ``tls``: TLS encryption. Used only for the client-to-PIM-server connection,
  authenticated with a bearer token rather than a client certificate.
* ``mtls``: mutual TLS, authenticated with a client certificate, a private
  key, and a certificate authority (CA) file.
* ``uds``: Unix domain socket. Only available on platforms and gRPC versions
  that support it.
* ``wnua``: Windows named user authentication. Windows only, and only for
  local connections.

********************************************
Securing the client-to-PIM-server connection
********************************************

This is the connection created by :func:`connect`. It can be configured
either through a configuration file or programmatically.

Configuration file
==================

The configuration file referenced by the
``ANSYS_PLATFORM_INSTANCEMANAGEMENT_CONFIG`` environment variable has two
supported formats.

Version 1 (``tls`` boolean)
---------------------------

The original format supports only ``insecure`` and ``tls``:

.. code-block:: json

    {
        "version": 1,
        "pim": {
            "uri": "dns:pim.svc.com:80",
            "headers": {
                "authorization": "Bearer <token>"
            },
            "tls": true
        }
    }

When ``tls`` is ``true``, the ``authorization`` header must contain a
``Bearer`` token, which is used to build the secure channel credentials. This
format continues to work unchanged; it is never removed by adding version 2
support.

Version 2 (``security`` block)
------------------------------

The version 2 format replaces the ``tls`` boolean with a ``security`` block
that can select any of the five transports:

.. code-block:: json

    {
        "version": 2,
        "pim": {
            "uri": "dns:pim.svc.com:80",
            "headers": {
                "metadata-info": "value"
            },
            "security": {
                "transport": "mtls",
                "certificate_files": {
                    "cert_file": "client.crt",
                    "key_file": "client.key",
                    "ca_file": "ca.crt"
                }
            }
        }
    }

The ``security.transport`` value must be one of ``insecure``, ``tls``,
``uds``, ``mtls``, or ``wnua``.

* For ``tls``, the ``authorization`` header must still contain a ``Bearer``
  token, exactly as in version 1.
* For ``mtls``, provide client certificates either as individual files with
  ``certificate_files`` (``cert_file``, ``key_file``, and ``ca_file``, all
  required together) or as a ``certificates_directory`` path. Provide at
  most one of the two; providing neither is valid and lets the underlying
  transport layer resolve its own defaults.
* For ``uds``, the socket path is taken directly from a ``unix:`` ``uri``.
  Because the PIM server is expected to already be listening on that socket,
  the socket path is checked for existence when the configuration is loaded.
* For ``wnua`` and ``insecure``, no additional ``security`` fields are
  needed.

Any misconfiguration (an unknown transport, conflicting mTLS certificate
options, a missing UDS socket, or a missing bearer token for ``tls``) raises
:class:`InvalidConfigurationError` as soon as the configuration is loaded,
rather than failing later on the first request.

Programmatic configuration
==========================

When no configuration file is present, :func:`connect` accepts the
connection settings directly:

.. code-block:: python

    import ansys.platform.instancemanagement as pypim
    from ansys.platform.instancemanagement import ConnectionSecurity
    from ansys.tools.common.cyberchannel import CertificateFiles

    client = pypim.connect(
        uri="dns:pim.svc.com:80",
        headers={"identity": "james"},
        security=ConnectionSecurity(
            transport="mtls",
            cert_files=CertificateFiles(
                cert_file="client.crt", key_file="client.key", ca_file="ca.crt"
            ),
        ),
    )

:class:`ConnectionSecurity` mirrors the version 2 configuration file's
security options. Its ``transport`` is one of ``insecure``, ``tls``, ``uds``,
``mtls``, or ``wnua``. For ``mtls``, provide client certificates as either
``cert_files`` (a ``CertificateFiles``) *or* ``certs_dir`` (a directory path),
but not both; providing neither is valid and lets the underlying transport
layer resolve its own defaults. An invalid combination raises ``ValueError``
at construction time.

Precedence between the configuration file and these parameters is
**file-exclusive and all-or-nothing**: if the environment is configured with
a configuration file (:func:`is_configured` is ``True``), that file is used
in full and the ``uri``, ``headers``, and ``security`` parameters are
ignored entirely. The parameters are used only when there is no
configuration file. If neither a file nor a ``uri`` parameter is available,
:func:`connect` raises :class:`NotConfiguredError`.

***************************************
Securing a product instance at creation
***************************************

:func:`Client.create_instance` accepts an optional ``security_settings``
parameter describing which transport the PIM server should use to expose the
created instance:

.. code-block:: python

    import ansys.platform.instancemanagement as pypim
    from ansys.platform.instancemanagement import MtlsSettings

    client = pypim.connect()
    instance = client.create_instance(
        product_name="mapdl",
        security_settings=MtlsSettings(certificates_directory="/path/to/certs"),
    )

``security_settings`` accepts one of:

* :class:`InsecureSettings`: no transport security (the default when
  ``security_settings`` is not provided; the actual choice is up to the PIM
  server).
* :class:`MtlsSettings`: mutual TLS, with certificates provided either as a
  ``certificates_directory`` or as individual ``certificate_paths``
  (:class:`MtlsCertificatePaths`).
* :class:`UdsSettings`: Unix domain socket, with the socket location
  provided either as a full ``socket_path`` or as a ``socket_directory`` /
  ``socket_identifier`` pair.
* :class:`WnuaSettings`: Windows named user authentication. Windows only.

For :class:`MtlsSettings` and :class:`UdsSettings`, supplying a conflicting
combination of options (for example both certificate sources, or a
``socket_path`` together with a ``socket_directory``) raises ``ValueError``
at construction time.

These settings are a *request*: the PIM server ultimately decides what
transport the instance is actually exposed with, and communicates that
choice back through the instance's services (see the next section).

****************************************
Reading security settings from a service
****************************************

Once an instance is ready, each entry in :attr:`Instance.services` is a
:class:`Service` describing how to reach that particular endpoint. When the
server reports transport security for a service, :attr:`Service.transport`
exposes the resolved transport name (one of ``insecure``, ``uds``, ``mtls``,
or ``wnua``), or ``None`` when the server did not report any security
information for that service:

.. code-block:: python

    instance.wait_for_ready()
    service = instance.services["grpc"]
    print(service.transport)  # e.g. "mtls"

You do not need to build the gRPC channel yourself based on this
information: :func:`Instance.build_grpc_channel` reads the resolved
transport (and, for ``mtls``, the client certificate files) and builds a
correctly secured channel automatically.
