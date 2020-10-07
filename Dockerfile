# This is intended to run in Github Actions
# Arg can be set to dev for testing purposes
ARG BUILD_ENV="prod"
ARG MAINTAINER="kimn@ssi.dk;"
ARG BIFROST_COMPONENT_NAME="bifrost_run_launcher"

# For dev build include testing modules via pytest done on github and in development.
# Watchdog is included for docker development (intended method) and should preform auto testing 
# while working on *.py files
FROM continuumio/miniconda3:4.7.10 as build_dev
ONBUILD ARG BIFROST_COMPONENT_NAME
ONBUILD COPY . /${BIFROST_COMPONENT_NAME}
ONBUILD WORKDIR ${BIFROST_COMPONENT_NAME}
ONBUILD RUN \
    git clone https://github.com/ssi-dk/bifrost_test_data.git /bifrost_test_data; \
    pip install -r requirements.dev.txt;

FROM continuumio/miniconda3:4.7.10 as build_prod
ONBUILD ARG BIFROST_COMPONENT_NAME
ONBUILD COPY . /${BIFROST_COMPONENT_NAME}
ONBUILD WORKDIR ${BIFROST_COMPONENT_NAME}
ONBUILD RUN \
    pip install -r requirements.txt

#- Use development or production to and add info: start---------------------------------------------
FROM build_${BUILD_ENV}
ARG BIFROST_COMPONENT_NAME
LABEL \
    BIFROST_COMPONENT_NAME=${BIFROST_COMPONENT_NAME} \
    description="Docker environment for ${BIFROST_COMPONENT_NAME}" \
    environment="${BUILD_ENV}" \
    maintainer="${MAINTAINER}"
#- Use development or production to and add info: end-----------------------------------------------


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
WORKDIR ${BIFROST_COMPONENT_NAME}
ENTRYPOINT ["python3", "-m", "bifrost_run_launcher"]
CMD ["python3", "-m", "bifrost_run_launcher", "--help"]
#- Set up entry point:end --------------------------------------------------------------------------