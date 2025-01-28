import setuptools


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


setuptools.setup(
    name="eoapi-maps-plugin",
    version="0.0.1",
    author="Nikola Jankovic",
    author_email="nikola.jankovic@eox.com",
    description="OGC API - Maps plugin for pygeoapi using eoAPI",
    license="MIT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/EOEPCA/eoapi-maps-plugin",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
