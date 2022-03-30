from setuptools import setup, find_packages

setup(
    name="ansys-platform-instancemanagement",
    version="0.1.dev0",
    description="A Python wrapper for Ansys platform instancemanagement",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
)
