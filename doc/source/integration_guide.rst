###################
 Integration Guide
###################

.. currentmodule:: ansys.platform.instancemanagement

Even though PyPIM can be used by an application developer, it is also intended
to be used behind the scene by other PyAnsys libraries to manage a remote
instance of the product they interact with. This enables an application
developer to write code that works both in an environment configured with PyPIM,
or without.

For example an application developer can write the following code:

.. code:: python

   from ansys.mapdl.core import launch_mapdl

   mapdl = launch_mapdl()

Instead of:

.. code:: python

   import ansys.platform.instancemanagement as pypim
   from ansys.mapdl.core import launch_mapdl

   if pypim.is_configured():
       pim = pypim.connect()
       instance = pypim.create_instance(product_name="mapdl")
       channel = instance.build_grpc_channel(
           options=[("grpc.max_receive_message_length", 8 * 1024**2)]
       )
       mapdl = Mapdl(channel=channel)
   else:
       mapdl = launch_mapdl()

This guide exposes the guidelines to implement such ``launch_*`` method that
takes in account PyPIM. Just like the entire PIM API, this guide is only
targeted toward products that are stateful and require explicit lifecycle
management.

*************
 Integration
*************

Dependency
==========

``PyPIM`` is following semantic versioning. A library should depend on pypim
with the following ``require`` string:

``"ansys-platform-instancemanagement~=1.0"``

Condition to use PyPIM
======================

Using PyPIM is done transparently under certain conditions. The condition should
be that the user requests to launch the product in an environment configured
with PyPIM, without specifying an intent on how it should be launched, then
PyPIM should be used. In other words, PyPIM should be the default startup method
in an environment configured for PyPIM.

Thus the right place for integrating it is a generic method such as
``launch_my_product()``, or a constructor that usually is able to start a local
process.

For example, with PyMAPDL in an environment configured with PyPIM, the following
code uses PyPIM:

.. code:: python

   from ansys.mapdl.core import launch_mapdl

   mapdl = launch_mapdl()

But this code will not use PyPIM:

.. code:: python

   from ansys.mapdl.core import launch_mapdl

   mapdl = launch_mapdl(exec_file="/usr/bin/mapdl")

Starting a gRPC product
=======================

When PyPIM is used, the code flow should be:

First, check if pypim is configured with :func:`is_configured` and the user has not
given any indication on how to start it. If both conditions are met:

#. Connect to pypim with :func:`connect`
#. Create an instance with :func:`Client.create_instance`
#. Wait for the instance to be ready with :func:`Instance.wait_for_ready`
#. Build a gRPC channel with :func:`Instance.build_grpc_channel`

Typically, the resulting code will look like:

.. code:: python

   import ansys.platform.instancemanagement as pypim

   def launch_my_product(self, ...):
       if pypim.is_configured() and not user_has_specified_how_to_launch_the_product:
           pim = pypim.connect()
           self.instance = pypim.create_instance("my_product_name")
           self.instance.wait_for_ready()
           channel = self.instance.build_grpc_channel()
       else:
           # usual start-up
           self.process = subprocess.run(...)
           channel = grpc.insecure_chanel(...)

When stopping the product, the remote instance should also be deleted:

.. code:: python

   def stop(self):
       if self.instance is not None:
           self.instance.delete()

Note that it is the responsibility of the PIM to clean-up any resource and
process associated with the product. It's however fine to double down with any
relevant product specific clean-up.

Starting a non gRPC product
===========================

The code flow is the same, but the connection will be more specific.

For a REST product, the base uri will be found under
``instance.services["http"].uri`` and all the requests must include the headers
found in ``instance.services["http"].headers``.

For another protocol, it will be up to an agreement between the PIM
implementation and the client code to pass the required information in a
dedicated entry in ``.services``.

********
 Testing
********

When testing the PyPIM integration, it is advised not to rely on any actual PIM
implementation. Instead we recommend to mock the interaction with PyPIM.
Verifying that a specific PIM implementation is able to start and provide an
endpoint to the product in a specific environment is the responsibility of the
team managing this environment.

This test approach mocks PyPIM behavior, resulting in a verbose test with no
additional dependencies. It is also not subject to bugs in PyPIM or in a PIM
implementation.

The initial setup of such mock can look like:

.. code:: python

    from unittest.mock import create_autospec
    import grpc
    import ansys.platform.instancemanagement as pypim


    def test_pim(monkeypatch):
        # Actually start the product
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

        # Mock the PyPIM client, so that on the "create_instance" call it returns the mock instance
        # Note: the host and port here will not be used.
        mock_client = pypim.Client(channel=grpc.insecure_channel("localhost:12345"))
        mock_client.create_instance = create_autospec(
            mock_client.create_instance, return_value=mock_instance
        )

        # Mock the general pypim connection and configuration check method to expose the mock client.
        mock_connect = create_autospec(pypim.connect, return_value=mock_client)
        mock_is_configured = create_autospec(pypim.is_configured, return_value=True)
        monkeypatch.setattr(pypim, "connect", mock_connect)
        monkeypatch.setattr(pypim, "is_configured", mock_is_configured)

This initial setup is faking all the necessary parts of PyPIM. From here,
calling ``launch_my_product()`` with no parameter is expected to only call the
mocks, which the test should now do:

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

********
 Example
********

An example of such integration can be seen `in PyMAPDL <https://github.com/pyansys/pymapdl/pull/1091/files>`_.
