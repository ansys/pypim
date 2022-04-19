============
Contributing
============

The general guidance is available in the `Contributing` topic in the *PyAnsys
Developer's Guide*. PyPIM follows the PyAnsys `Guidelines and Best Practices`_.

.. _`Contributing`: https://dev.docs.pyansys.com/overview/contributing.html
.. _`Guidelines and Best Practices`: https://dev.docs.pyansys.com/guidelines/index.html


Cloning the PyPIM Repository
----------------------------

.. code-block::
    
    git clone https://github.com/pyansys/pypim.git
    cd pypim/

Running the tests
-----------------

The test automation relies on `tox`.

They are entirely based on mocks and do not require any external software. Run
the tests with:

.. code-block::
    
    tox -e py38

Where py38 matches your python version.

.. _`tox`: https://tox.wiki/en/latest/install.html#installation-with-pip

Building the documentation
--------------------------

.. code-block::
    
    tox -e doc

Building the package
--------------------

The package is built using `flit`.

You can build the PyPIM package with:

.. code-block::
    
    flit build

You can also directly install PyPIM in your current environment with:

.. code-block::
    
    flit install

.. _`flit`: https://flit.pypa.io/en/latest/#install

Release Process
---------------

PyPIM follows the same `branching model`_ as other PyAnsys libraries, and its
`release procedure`_.

The only notable difference is that the documentation is created with ``tox -e
doc`` instead of using ``make``.

.. _`branching model`: https://dev.docs.pyansys.com/guidelines/dev_practices.html#branching-model
.. _`release procedure`: https://dev.docs.pyansys.com/guidelines/dev_practices.html#release-procedures
