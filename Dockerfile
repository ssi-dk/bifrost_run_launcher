# This is intended to run in Github Actions
# Arg can be set to dev for testing purposes
ARG BUILD_ENV="prod"
ARG NAME="bifrost_run_launcher"
ARG CODE_VERSION="unspecified"
ARG RESOURCE_VERSION="unspecified"

#For dev build include testing modules
FROM continuumio/miniconda3:4.7.10 as build_dev
ONBUILD ARG NAME
ONBUILD RUN pip install pytest \
    pytest-cov \
    pytest-profiling \
    coverage;
ONBUILD COPY tests /${NAME}/tests
ONBUILD COPY examples /${NAME}/examples

FROM continuumio/miniconda3:4.7.10 as build_prod
ONBUILD ARG NAME
ONBUILD RUN echo ${BUILD_ENV}

FROM build_${BUILD_ENV}
ARG NAME
LABEL \
    name=${NAME} \
    description="Docker environment for ${NAME}" \
    code_version="${CODE_VERSION}" \
    resource_version="${RESOURCE_VERSION}" \
    environment="${BUILD_ENV}" \
    maintainer="kimn@ssi.dk;"

#- Tools to install:start---------------------------------------------------------------------------
# None
#- Tools to install:end ----------------------------------------------------------------------------

#- Additional resources (files/DBs): start ---------------------------------------------------------
# None
#- Additional resources (files/DBs): end -----------------------------------------------------------

#- Source code:start -------------------------------------------------------------------------------
# COPY src /${NAME}/src
COPY ${NAME} /${NAME}/${NAME}
COPY setup.py /${NAME}
RUN \
    sed -i'' 's/<code_version>/'"${CODE_VERSION}"'/g' /${NAME}/${NAME}/config.yaml; \
    sed -i'' 's/<resource_version>/'"${RESOURCE_VERSION}"'/g' /${NAME}/${NAME}/config.yaml; \
    cd /${NAME}; \
    pip install . 
#- Source code:end ---------------------------------------------------------------------------------

#- Set up entry point:start ------------------------------------------------------------------------
ENTRYPOINT ["python3 -m bifrost_run_launcher"]
CMD ["python3 -m bifrost_run_launcher", "--help"]
#- Set up entry point:end --------------------------------------------------------------------------