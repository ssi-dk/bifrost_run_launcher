# This is intended to run in Github Actions
# Arg can be set to dev for testing purposes
ARG BUILD_ENV="prod"
ARG NAME="bifrost_run_launcher"
ARG CODE_VERSION="unspecified"
ARG RESOURCE_VERSION="unspecified"
ARG MAINTAINER="kimn@ssi.dk;"

# For dev build include testing modules via pytest done on github and in development.
# Watchdog is included for docker development (intended method) and should preform auto testing 
# while working on *.py files
FROM continuumio/miniconda3:4.7.10 as build_dev
ONBUILD ARG NAME
# Acquire test data
ONBUILD RUN \
    git clone https://github.com/ssi-dk/bifrost_test_data.git
ONBUILD COPY . /${NAME}
ONBUILD WORKDIR ${NAME}
ONBUILD RUN \
    sed -i'' 's/<code_version>/'"${CODE_VERSION}"'/g' ${NAME}/config.yaml; \
    sed -i'' 's/<resource_version>/'"${RESOURCE_VERSION}"'/g' ${NAME}/config.yaml; \
    pip install -r requirements.dev.txt;

FROM continuumio/miniconda3:4.7.10 as build_prod
ONBUILD ARG NAME
ONBUILD WORKDIR ${NAME}
ONBUILD COPY ${NAME} ${NAME}
ONBUILD COPY setup.py setup.py
ONBUILD COPY requirements.txt requirements.txt
ONBUILD RUN \
    sed -i'' 's/<code_version>/'"${CODE_VERSION}"'/g' ${NAME}/config.yaml; \
    sed -i'' 's/<resource_version>/'"${RESOURCE_VERSION}"'/g' ${NAME}/config.yaml; \
    ls; \
    pip install -r requirements.txt

FROM build_${BUILD_ENV}
ARG NAME
LABEL \
    name=${NAME} \
    description="Docker environment for ${NAME}" \
    code_version="${CODE_VERSION}" \
    resource_version="${RESOURCE_VERSION}" \
    environment="${BUILD_ENV}" \
    maintainer="${MAINTAINER}"

#- Tools to install:start---------------------------------------------------------------------------
# None
#- Tools to install:end ----------------------------------------------------------------------------

#- Additional resources (files/DBs): start ---------------------------------------------------------
# None
#- Additional resources (files/DBs): end -----------------------------------------------------------

#- Source code:start -------------------------------------------------------------------------------
# 
#- Source code:end ---------------------------------------------------------------------------------

#- Set up entry point:start ------------------------------------------------------------------------
ENTRYPOINT ["python3", "-m", "bifrost_run_launcher"]
CMD ["python3", "-m", "bifrost_run_launcher", "--help"]
#- Set up entry point:end --------------------------------------------------------------------------