# This is intended to run in Local Development (dev) and Github Actions (test/prod)
# BUILD_ENV options (dev, test, prod) dev for local testing and test for github actions testing on prod ready code
ARG BUILD_ENV="prod"
ARG MAINTAINER="kimn@ssi.dk;"
ARG BIFROST_COMPONENT_NAME="bifrost_run_launcher"

#---------------------------------------------------------------------------------------------------
# Base for dev environement
#---------------------------------------------------------------------------------------------------
FROM continuumio/miniconda3:4.8.2 as build_dev
ONBUILD ARG BIFROST_COMPONENT_NAME
ONBUILD COPY /components/${BIFROST_COMPONENT_NAME} /bifrost/components/${BIFROST_COMPONENT_NAME}
ONBUILD COPY /lib/bifrostlib /bifrost/lib/bifrostlib
ONBUILD WORKDIR /bifrost/components/${BIFROST_COMPONENT_NAME}/
ONBUILD RUN \
    pip install -r requirements.txt; \
    pip install --no-cache -e file:///bifrost/lib/bifrostlib; \
    pip install --no-cache -e file:///bifrost/components/${BIFROST_COMPONENT_NAME}/

#---------------------------------------------------------------------------------------------------
# Base for production environment
#---------------------------------------------------------------------------------------------------
FROM continuumio/miniconda3:4.8.2 as build_prod
ONBUILD ARG BIFROST_COMPONENT_NAME
ONBUILD WORKDIR /bifrost/components/${BIFROST_COMPONENT_NAME}
ONBUILD COPY ./ ./
ONBUILD RUN \
    pip install -r requirements.txt; \
    pip install file:///bifrost/components/${BIFROST_COMPONENT_NAME}/

#---------------------------------------------------------------------------------------------------
# Base for test environment (prod with tests)
#---------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------
FROM continuumio/miniconda3:4.8.2 as build_test
ONBUILD ARG BIFROST_COMPONENT_NAME
ONBUILD WORKDIR /bifrost/components/${BIFROST_COMPONENT_NAME}
ONBUILD COPY ./ ./
ONBUILD RUN \
    pip install -r requirements.txt \
    pip install file:///bifrost/components/${BIFROST_COMPONENT_NAME}/

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

#---------------------------------------------------------------------------------------------------
# Additional programs for all environments
#---------------------------------------------------------------------------------------------------
# N/A

#---------------------------------------------------------------------------------------------------
# Additional resources
#---------------------------------------------------------------------------------------------------
# N/A

#---------------------------------------------------------------------------------------------------
# Run and entry commands
#---------------------------------------------------------------------------------------------------
WORKDIR /bifrost/components/${BIFROST_COMPONENT_NAME}
ENTRYPOINT ["python3", "-m", "bifrost_run_launcher"]
CMD ["python3", "-m", "bifrost_run_launcher", "--help"]
