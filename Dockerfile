# This is intended to run in Github Actions
# Arg can be set to dev for testing purposes
ARG BUILD_ENV="prod"

#For dev build include testing modules
FROM continuumio/miniconda3:4.7.10 as build_dev
ONBUILD RUN pip install pytest \
                        pytest-cov \
                        pytest-profiling \
                        coverage;

FROM continuumio/miniconda3:4.7.10 as build_prod
ONBUILD RUN echo ${BUILD_ENV}

FROM build_${BUILD_ENV}
ARG NAME="bifrost-run_launcher"
ARG CODE_VERSION
ARG RESOURCE_VERSION

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
COPY src /bifrost/src
RUN \
    pip install bifrostlib==2.0.7; \
    sed -i'' 's/<code_version>/'"${CODE_VERSION}"'/g' /bifrost/src/config.yaml; \
    sed -i'' 's/<resource_version>/'"${RESOURCE_VERSION}"'/g' /bifrost/src/config.yaml;
#- Source code:end ---------------------------------------------------------------------------------

#- Set up entry point:start ------------------------------------------------------------------------
ENV PATH /bifrost/src/:$PATH
ENTRYPOINT ["/bifrost/src/launcher.py"]
CMD ["/bifrost/src/launcher.py", "--help"]
#- Set up entry point:end --------------------------------------------------------------------------