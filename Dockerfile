# This is intended to run in Local Development (dev) and Github Actions (test/prod)
# BUILD_ENV options (dev, test, prod) dev for local testing and test for github actions testing on prod ready code
ARG BUILD_ENV="prod"
ARG MAINTAINER="kimn@ssi.dk;"
ARG BIFROST_COMPONENT_NAME="bifrost_run_launcher"

#---------------------------------------------------------------------------------------------------
# Base for dev environement
#---------------------------------------------------------------------------------------------------
FROM continuumio/miniconda3:22.11.1 as build_dev
ONBUILD ARG BIFROST_COMPONENT_NAME
ONBUILD COPY /components/${BIFROST_COMPONENT_NAME} /bifrost/components/${BIFROST_COMPONENT_NAME}
ONBUILD COPY /lib/bifrostlib /bifrost/lib/bifrostlib
ONBUILD WORKDIR /bifrost/components/${BIFROST_COMPONENT_NAME}/
ONBUILD RUN \
    conda env create -n run_launcher -f environment.yml && \
    conda run -n run_launcher pip install -e /bifrost/lib/bifrostlib && \
    conda run -n run_launcher pip install -e /bifrost/components/${BIFROST_COMPONENT_NAME}

#---------------------------------------------------------------------------------------------------
# Base for production environment
#---------------------------------------------------------------------------------------------------
FROM continuumio/miniconda3:22.11.1 as build_prod
ONBUILD ARG BIFROST_COMPONENT_NAME
ONBUILD WORKDIR /bifrost/components/${BIFROST_COMPONENT_NAME}
ONBUILD COPY ./ ./
ONBUILD RUN \
    conda env create -n run_launcher -f environment.yml && \
    conda run -n run_launcher pip install file:///bifrost/components/${BIFROST_COMPONENT_NAME} && \
    conda clean -ay

#---------------------------------------------------------------------------------------------------
# Base for test environment (prod with tests)
#---------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------
FROM continuumio/miniconda3:22.11.1 as build_test
ONBUILD ARG BIFROST_COMPONENT_NAME
ONBUILD WORKDIR /bifrost/components/${BIFROST_COMPONENT_NAME}
ONBUILD COPY ./ ./
ONBUILD RUN \
    conda env create -n run_launcher -f environment.yml && \
    conda run -n run_launcher pip install file:///bifrost/components/${BIFROST_COMPONENT_NAME} && \
    conda clean -ay

#---------------------------------------------------------------------------------------------------
# Details
#---------------------------------------------------------------------------------------------------
FROM build_${BUILD_ENV}
ONBUILD ARG BIFROST_COMPONENT_NAME
ONBUILD ARG BUILD_ENV
ONBUILD ARG MAINTAINER
LABEL \
    BIFROST_COMPONENT_NAME=${BIFROST_COMPONENT_NAME} \
    description="Docker environment for ${BIFROST_COMPONENT_NAME}" \
    environment="${BUILD_ENV}" \
    maintainer="${MAINTAINER}"

#ensure the python3 use the conda environment created above
ENV PATH="/opt/conda/envs/run_launcher/bin:${PATH}"

WORKDIR /bifrost/components/${BIFROST_COMPONENT_NAME}
ENTRYPOINT ["python3", "-m", "bifrost_run_launcher"]
CMD ["--help"]

