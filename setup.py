from setuptools import setup, find_packages
import os
import re

with open(f"{os.getenv('BIFROST_COMPONENT_NAME')}/config.yaml", "r") as config_stream:
    buffer = config_stream.read()

code_version = re.search("version:\n.*\n\s+code:\s*(?P<code_version>.*)\n\s+resource:\s*(?P<resource_version>.*)", buffer, re.MULTILINE).group("code_version")

component = {
    "name": os.getenv('BIFROST_COMPONENT_NAME'),
    "version": code_version
}

setup(
    name=component['name'],
    version=component['version'],
    url=f"https://github.com/ssi-dk/{component['name']}",

    # Author details
    author='Kim Ng',
    author_email='kimn@ssi.dk',

    # Choose your license
    license='MIT',

    packages=find_packages(),
    python_requires='>=3.6',

    package_data={component['name']: ['config.yaml']},
    include_package_data=True,

    install_requires=[
        'bifrostlib==2.0.11'
    ]
)
