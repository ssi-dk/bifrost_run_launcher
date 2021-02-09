from setuptools import setup, find_packages

setup(
    name='bifrost_run_launcher',
    version='v2_2_1',
    description='Datahandling functions for bifrost (later to be API interface)',
    url='https://github.com/ssi-dk/bifrost_run_launcher',
    author="Kim Ng, Martin Basterrechea",
    author_email="kimn@ssi.dk",
    packages=find_packages(),
    install_requires=[
        'bifrostlib >= 2.1.4',
    ],
    package_data={"bifrost_run_launcher": ['config.yaml']},
    include_package_data=True
    )
