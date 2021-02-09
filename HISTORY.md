# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
## [2.2.2] - 2021-01-11
Updates to bifrostlib to make it work with the tests and update to the tests so that they work with CI/CD which lacks access to bifrost/test_data

### Changed
- setup.cfg
- .github/workflows/run_test.yml
## [2.2.1] - 2020-12-14
### Notes
Development has adjusted from dev/prod on github to test/prod. Test for testing and prod for live code. Dev is now local and utilizes the whole bifrost folder structure while test/prod only utilizes the submodule structure. Currently tests have not been updated to reflect this change.

### Added
For added version bump and test init
- setup.cfg 

### Changed
- tests moved from /bifrost_run_launcher/ to /tests
- doc structure added but not set up
-  
Adjusted format of docker to work in context to root folder of project for local development /bifrost/ and to the submodule to prod. New environment test also is created for testing prod ready code on github actions with CI. 
  - Dockerfile
  - docker_build_and_push_to_dockerhub.yml
  - test_standard_workflow.yml
Requirements are now for pytest and environmental values, actual required python libraries are included in setup.py and required programs in the Dockerfile
  - requirements.txt
  - setup.py
Adjust code to reflect new bifrostlib==2.1.0 which has a new data structure and schema for the objects
- __main__.py
- config.yaml
- launcher.py
- test_1_standard_workflow.py

### Removed
Development is now local and the dockerfile for compose on the root /bifrost/ folder instead of at each submodule
- docker-compose.dev.yaml
- docker-compose.yaml
Now unnecessary as requirements merged with setup.py
- requirements.dev.txt
- .env


## [2.2.0] - 2020-10-07 (Unreleased)
### Added
- CHANGELOG.md into repo

### Changed
- Templated files to be common for SSI maintained pipelines. All files use .env and <COMPONENT_NAME>/config.yaml as the source of all information. The config.yaml should be considered the primary source of all information regarding the component and it's settings. The .env file needs to contain the <COMPONENT_NAME> and install specific settings (currently just mongo_db connection). 
  - docker-compose.dev.yaml
  - docker-compose.yaml
  - .env
    - This is being used for both Dockerfile and passing the values into the Docker image, not sure if that has any issues.
  - setup.py
    - This can't use libraries to extract config values, so right now it's hardcoded on what to look for. This can cause some potential issues.
- The following files are also impacted by the changes
  - Dockerfile

### Removed
- Docker-compose files no longer point to a custom env file