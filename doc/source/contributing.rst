==========
Contribute
==========

Overall guidance on contributing to a PyAnsys repository appears in the
`Contributing`_ topic in the *PyAnsys Developer's Guide*. Ensure that you are
thoroughly familiar with this guide before attempting to contribute to PyPIM.

.. _`Contributing`: https://dev.docs.pyansys.com/how-to/contributing.html

The following contribution information is specific to PyPIM.

Clone the PyPIM repository
--------------------------
To clone and install the latest version of PyPIM in development mode, run this code:

.. code-block::

    git clone https://github.com/pyansys/pypim.git
    cd pypim/

Run tests
---------
Test automation relies on `tox`_, which can be installed with this command:

.. code-block::

    pip install tox


Tests are entirely based on mocks and do not require any external software. Run
the tests with this command:

.. code-block::

    tox -e py


.. _`tox`: https://tox.wiki/en/latest/install.html#installation-with-pip

Build the documentation
-----------------------
You can build PyPIM documentation with this command:

.. code-block::

    tox -e doc

Build the package
-----------------

The PyPIM package is built using `flit`_.

To build the package, use this command:

.. code-block::

    flit build


You can also directly install PyPIM in your current environment with
this command:

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
