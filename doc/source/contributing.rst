============
Contributing
============

Overall guidance on contributing to a PyAnsys repository appears in the
`Contributing`_ topic in the *PyAnsys Developer's Guide*. Ensure that you are
thoroughly familiar with it and all `Guidelines and Best Practices`_
before attempting to contribute to PyPIM.
 
.. _`Contributing`: https://dev.docs.pyansys.com/overview/contributing.html
.. _`Guidelines and Best Practices`: https://dev.docs.pyansys.com/guidelines/index.html

The following contribution information is specific to PyPIM.

Cloning the PyPIM repository
----------------------------
Run this code to clone and install the latest version of PyPIM in development mode:

.. code-block::
    
    git clone https://github.com/pyansys/pypim.git
    cd pypim/

Running tests
-------------
Test automation relies on `tox`_, which can be installed with:

.. code-block::

    pip install tox


Tests are entirely based on mocks and do not require any external software. Run
the tests with the following code:

.. code-block::
    
    tox -e py

.. _`tox`: https://tox.wiki/en/latest/install.html#installation-with-pip

Building the documentation
--------------------------
You can build PyPIM documentation with:

.. code-block::
    
    tox -e doc

Building the package
--------------------

The PyPIM package is built using `flit`.

You can build the package with:

.. code-block::
    
    flit build

You can also directly install PyPIM in your current environment with:

.. code-block::
    
    flit install

.. _`flit`: https://flit.pypa.io/en/latest/#install

Release process
---------------
PyPIM follows the same `branching model`_ as other PyAnsys libraries and the
same `release procedure`_.

The only notable difference is that the documentation is created with ``tox -e
doc`` rather than with ``make``.

.. _`branching model`: https://dev.docs.pyansys.com/guidelines/dev_practices.html#branching-model
.. _`release procedure`: https://dev.docs.pyansys.com/guidelines/dev_practices.html#release-procedures
