=====
PyPIM
=====
|PyPI| |codecov| |CI| |MIT| |black|

.. |PyPI| image:: https://img.shields.io/pypi/v/ansys-platform-instancemanagement
    :target: https://pypi.org/project/ansys-platform-instancemanagement/
    :alt: PyPI

.. |codecov| image:: https://codecov.io/gh/pyansys/pypim/branch/main/graph/badge.svg
   :target: https://codecov.io/gh/pyansys/pypim
   :alt: Code Coverage

.. |CI| image:: https://img.shields.io/github/workflow/status/pyansys/pypim/GitHub%20CI/main
    :target: https://github.com/pyansys/pypim/actions/workflows/ci_cd.yml
    :alt: GitHub Workflow Status (branch)

.. |MIT| image:: https://img.shields.io/badge/License-MIT-yellow.svg
   :target: https://opensource.org/licenses/MIT
   :alt: MIT License

.. |black| image:: https://img.shields.io/badge/code%20style-black-000000.svg?style=flat
  :target: https://github.com/psf/black
  :alt: black
    
PyPIM exposes a Pythonic interface to communicate with the Product Instance
Management (PIM) API.

What is the PIM API?
============================================

The PIM API is a gRPC API enabling library and application developers to
start a product in a remote environment and communicate with its API.

The PIM API is intended to be as simple as possible to be adaptable in a variety of
network and software infrastructures. Using this API does not require any
knowledge of its infrastructure. You need only know which product to
start and which API the product exposes. The API itself exposes very few
features and assumes that all the configuration is set on a server.

The PIM API is not intended to manage stateless services, to be a job management
system, or a fully featured service orchestration API. Its purpose is to expose
a minimum feature set for managing service-oriented applications.

Getting Started
===============
To use PyPIM, you must have access to the PIM API.

.. note::
    PyPIM is a work in progress. There is no public expossure or
    distribution of an implementation yet.

PyPIM itself is pure Python and relies on `gRPC`_.

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

To start MAPDL and communicate with PyPIM:

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

You can also use PyPIM without the ``with`` statement:

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
