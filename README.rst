=====
PyPIM
=====

PyPIM exposes a pythonic interface to communicate with the Product Instance
Management API.

What is the Product Instance Management API?
============================================

The Product Instance Management API is a gRPC API enabling library and
application developers to start a product in a remote environment and
communicate with its API.

It is intended to be as simple as possible to be adaptable in a variety of
network and software infrastructure. Using this API does not require any
knowledge on this infrastructure, we want users to only know which product to
start, and which API the product exposes. The API itself exposes very little
feature and assumes that all the configuration is set on a server.

It is not intended to manage stateless services, to be a job management system,
or a fully featured service orchestration API, but rather to to expose a minimum
feature set of such API for service oriented applications.

Getting Started
===============

To use PyPIM, you need to have access to an exposition of the "Product
Instance Management" API.

.. note::
    This is a work in progress and there is no public exposition or
    distribution of an implementation yet.


PyPIM itself is pure python and relies on `gRPC`_.

.. _`gRPC`: https://grpc.io/

Installation
------------

The ``ansys-platform-instancemanagement`` package is tested for Python 3.7 through
Python 3.10 on Windows and Linux.

.. code-block::

    pip install ansys-platform-instancemanagement

Usage
-----

PyPIM is a single module called ``ansys.platform.instancemanagement``, shortened
to ``pypim``.

Starting MAPDL and communicating with it:

.. code-block::
    
    import ansys.platform.instancemanagement as pypim
    from ansys.mapdl.core import Mapdl
    
    if pypim.is_configured():
        with pypim.connect() as pim:
            with pim.create_instance(product_name="mapdl", product_version="221") as instance:
                instance.wait_for_ready()
                channel = instance.build_grpc_channel(options=[("grpc.max_receive_message_length", 8*1024**2)])
                mapdl = Mapdl(channel=channel)
                mapdl.prep7()
                ...

PyPIM can also be used without using the ``with`` statement:

.. code-block::
    
    import ansys.platform.instancemanagement as pypim
    from ansys.mapdl.core import Mapdl
    
    if pypim.is_configured():
        pim = pypim.connect()
        instance = pim.create_instance(product_name="mapdl", product_version="221")
        mapdl = Mapdl(channel=channel)
        mapdl.prep7()
        ...
        instance.delete()
        pim.close()
