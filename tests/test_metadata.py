from ansys.platform.instancemanagement import __version__


def test_pkg_version():
    assert __version__ == "1.0.3"
