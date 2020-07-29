from setuptools import setup, find_packages

setup(
    name='bifrost_run_launcher',
    version='v2.0.8',
    description='filters read against a small database of interest',
    url='https://github.com/ssi-dk/bifrost-run_launcher',

    # Author details
    author='Kim Ng',
    author_email='kimn@ssi.dk',

    # Choose your license
    license='MIT',

    packages=find_packages(),
    python_requires='>=3.6',

    package_data={'bifrost_run_launcher': ['config.yaml']},
    include_package_data=True,

    install_requires=[
        'bifrostlib==2.0.7'
    ]
)
