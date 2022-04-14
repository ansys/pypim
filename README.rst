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
Instance Management" API. This is currently a work in progress and there is
currently no public exposition or distribution of an implementation.

PyPIM itself is pure python and relies on `gRPC <https://grpc.io/>`_.

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
        pim=pypim.connect()
        instance = pim.create_instance(product_name="mapdl", product_version="221")
        instance.wait_for_ready()
        channel = instance.build_grpc_channel(options=[("grpc.max_receive_message_length", 8*1024**2)])
        mapdl = Mapdl(channel=channel)
        mapdl.prep7()
        ...
        instance.delete()

Developer Guide
===============

The general guidance appears in the `Contributing
<https://dev.docs.pyansys.com/overview/contributing.html>`_ topic in the
*PyAnsys Developer's Guide*.

Cloning the PyPIM Repository
----------------------------

.. code-block::
    
    git clone https://github.com/pyansys/pypim.git
    cd pypim/

Running the tests
-----------------

The test automation relies on `tox
<https://tox.wiki/en/latest/install.html#installation-with-pip>`_.

They are entirely based on mocks and do not require any external software. Run
the tests with:

.. code-block::
    
    tox -e py38

Where py38 matches your python version.

Building the documentation
--------------------------

.. code-block::
    
    tox -e doc

Building the package
--------------------

The package is built using `flit <https://flit.pypa.io/en/latest/#install>`_.

You can build the PyPIM package with:

.. code-block::
    
    flit build

You can also directly install PyPIM in your current environment with:

.. code-block::
    
    flit install

Release Process
---------------

Releasing a new version is driven by git tags, created from the Github release
page.

1. Create the release branch, named ``release/v<version>``, where version does
   not include the patch part. Eg. ``release/v0.5``, ``release/v1.2``
2. In the ``release/v<version>`` branch, remove the ``.dev0`` suffix in
   ``pyproject.toml`` and ``tests/test_metadata.py``
3. Create a `new release <https://github.com/pyansys/pypim/releases/new>`_ with
   a new tag named ``v<full_version>``, including the patch part, based on the latest
   commit of the ``release/v<version>`` branch. Eg. ``v0.5.0``, ``v1.2.0``.
4. In the ``main`` branch, increase the version, keeping the ``.dev0`` suffix.

Patch versions are created from their release branch, by cherry-picking commits.
