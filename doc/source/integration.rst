.. _integration:

###########
Integration
###########

.. currentmodule:: ansys.platform.instancemanagement

While PyPIM can be used by an app developer, it can also
be used behind the scene by other PyAnsys libraries to manage remote
instances of the products that they interact with. This enables an app
developer to write code that works both in an environment configured with PyPIM
and an environment without such a configuration.

For example, an app developer can write the following code:

.. code:: python

   from ansys.mapdl.core import launch_mapdl

   mapdl = launch_mapdl()

The preceding code replaces this much longer code:

.. code:: python

   import ansys.platform.instancemanagement as pypim
   from ansys.mapdl.core import launch_mapdl

   if pypim.is_configured():
       pim = pypim.connect()
       instance = pim.create_instance(product_name="mapdl")
       channel = instance.build_grpc_channel(
           options=[("grpc.max_receive_message_length", 8 * 1024**2)]
       )
       mapdl = Mapdl(channel=channel)
   else:
       mapdl = launch_mapdl()

This page provides guidelines for implementing the ``launch_*`` method that
takes PyPIM into account. Just like the entire PIM API, this page is targeted
only toward products that are stateful and require explicit lifecycle
management.

*****
Usage
*****

Dependency
==========

``PyPIM`` uses semantic versioning. To depend on PyPIM, a library
must include the following ``require`` string:

``"ansys-platform-instancemanagement~=1.0"``

Condition for PyPIM usage
=========================

The condition for using PyPIM transparently is that you must
be able to launch the product in an environment configured with PyPIM
without specifying launch information. In other words, PyPIM must be
the default startup method in an environment that is configured with PyPIM.

To integrate PyPIM correctly, you should use either a generic method such as
the ``launch_my_product()`` method or a constructor that usually starts a local process.

For example, with PyMAPDL in an environment configured with PyPIM, this
code uses PyPIM:

.. code:: python

   from ansys.mapdl.core import launch_mapdl

   mapdl = launch_mapdl()

However, this code does not use PyPIM:

.. code:: python

   from ansys.mapdl.core import launch_mapdl

   mapdl = launch_mapdl(exec_file="/usr/bin/mapdl")

Start a gRPC product
====================

To use PyPIM, the code flow should first check if PyPIM is configured
to use the :func:`is_configured` method and then check to ensure that the user has not
specified how to launch it.

If both conditions are met:

#. Connect to PyPIM with the :func:`connect` method.
#. Create an instance with :func:`Client.create_instance` method.
#. Wait for the instance to be ready with the :func:`Instance.wait_for_ready` method.
#. Build a gRPC channel with the :func:`Instance.build_grpc_channel` method.

Typically, the resulting code looks like this:

.. code:: python

   import ansys.platform.instancemanagement as pypim

   def launch_my_product(self, ...):
       if pypim.is_configured() and not user_has_specified_how_to_launch_the_product:
           pim = pypim.connect()
           self.instance = pim.create_instance("my_product_name")
           self.instance.wait_for_ready()
           channel = self.instance.build_grpc_channel()
       else:
           # usual start-up
           self.process = subprocess.run(...)
           channel = grpc.insecure_chanel(...)

When stopping the product, use this code to ensure that the remote instance
is deleted:

.. code:: python

   def stop(self):
       if self.instance is not None:
           self.instance.delete()

.. note::
   While it is PyPIM's responsibility to clean up any resource and
   process associated with the product, relevant product-specific cleanup
   can still be performed.

Start a Non-gRPC product
========================

While the code flow for a non-gRPC product is the same, connection information
is more specific.

* For a REST-ful product, the base uniform resource identifier (URI) must be
  found under ``instance.services["http"].uri`` and all requests must include the
  headers in ``instance.services["http"].headers``.

* For other protocols, an agreement between the PIM implementation and the
  client code determines how to pass the required information in a
  dedicated entry in ``.services``.

*******
Testing
*******

When testing the PyPIM integration, you should not rely on an actual PIM
implementation. Instead, you should mock the interaction with PyPIM.
Verifying that a specific PIM implementation is able to start and provide an
endpoint to the product in a specific environment is the responsibility of the
team managing this environment.

This test approach mocks PyPIM behavior, resulting in a verbose test with no
additional dependencies. It is also not subject to bugs in PyPIM or in a PIM
implementation.

The initial setup of such a mock can look like this:

.. code:: python

    from unittest.mock import create_autospec
    import grpc
    import ansys.platform.instancemanagement as pypim


    def test_pim(monkeypatch):
        # Start the product
        product = launch_my_product(port=50052)

        # Create a mock PyPIM instance object representing the running product
        mock_instance = pypim.Instance(
            definition_name="definitions/fake-product",
            name="instances/fake-product",
            ready=True,
            status_message=None,
            services={"grpc": pypim.Service(uri="localhost:50052", headers={})},
        )

        # Create a working gRPC channel to this product
        pim_channel = grpc.insecure_channel("localhost:50052")

        # Mock the wait_for_ready method so that it immediately returns
        mock_instance.wait_for_ready = create_autospec(mock_instance.wait_for_ready)

        # Mock the `build_grpc_channel` to return the working channel
        mock_instance.build_grpc_channel = create_autospec(
            mock_instance.build_grpc_channel, return_value=pim_channel
        )

        # Mock the deletion method
        mock_instance.delete = create_autospec(mock_instance.delete)

        # Mock the PyPIM client so that on the "create_instance" call it returns the mock instance
        # Note: the host and port here will not be used.
        mock_client = pypim.Client(channel=grpc.insecure_channel("localhost:12345"))
        mock_client.create_instance = create_autospec(
            mock_client.create_instance, return_value=mock_instance
        )

        # Mock the general PyPIM connection and configuration check method to expose the mock client.
        mock_connect = create_autospec(pypim.connect, return_value=mock_client)
        mock_is_configured = create_autospec(pypim.is_configured, return_value=True)
        monkeypatch.setattr(pypim, "connect", mock_connect)
        monkeypatch.setattr(pypim, "is_configured", mock_is_configured)


This initial setup is faking all the necessary parts of PyPIM. From here,
calling the ``launch_my_product()`` method with no parameter is expected
to call only the mocks, which the test should now do:

.. code:: python
    
    my_product = launch_my_product()


After this call, the test is ready to make all the assertions verifying that the PyPIM workflow was applied:

.. code:: python

    # The launch method checked if it was in a PyPIM environment
    assert mock_is_configured.called

    # It connected to PyPIM
    assert mock_connect.called

    # It created a remote instance through PyPIM
    mock_client.create_instance.assert_called_with(
        product_name="my_product_name", product_version=None
    )

    # It waited for this instance to be ready
    assert mock_instance.wait_for_ready.called

    # It created an gRPC channel from this instance
    assert mock_instance.build_grpc_channel.called

    # It connected using the channel created by PyPIM
    assert my_product._channel == pim_channel


When stopping the product, the test should also verify that the remote instance is deleted:

.. code:: python
    
    # Stop the product
    my_product.stop()
    
    assert mock_instance.delete.called


*******
Example
*******

An example of such an integration can be seen in this
`PyMAPDL pull request <https://github.com/pyansys/pymapdl/pull/1091/files>`_.
