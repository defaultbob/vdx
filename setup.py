# setup.py
from setuptools import setup, find_packages

setup(
    name="vdx",
    version="0.1.0",
    packages=find_packages(where="vdx_project"),
    package_dir={"": "vdx_project"},
    install_requires=[
        "requests",
    ],
    entry_points={
        "console_scripts": [
            "vdx=vdx.cli:main",
        ],
    },
)