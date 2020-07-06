# This is intended to run in Github Actions
FROM python:latest

ARG name="bifrost-run_launcher"
ARG code_version
ARG resource_version

LABEL \
    name=${name} \
    description="Docker environment for ${name}" \
    code_version="${code_version}" \
    resource_version="${resource_version}" \
    maintainer="kimn@ssi.dk;"

#- Tools to install:start---------------------------------------------------------------------------
# None
#- Tools to install:end ----------------------------------------------------------------------------

#- Additional resources (files/DBs): start ---------------------------------------------------------
# None
#- Additional resources (files/DBs): end -----------------------------------------------------------

#- Source code:start -------------------------------------------------------------------------------
COPY src /bifrost/src
#COPY resources /bifrost/resources
RUN \
    pip install -q bifrostlib==2.0.7; \
    sed 's/<code_version>/'"${code_version}"'/1' /bifrost/src/config.yaml > /bifrost/src/config.yaml; \
    sed 's/<resource_version>/'"${resource_version}"'/1' /bifrost/src/config.yaml > /bifrost/src/config.yaml;
    #- Source code:end ---------------------------------------------------------------------------------

#- Set up entry point:start ------------------------------------------------------------------------
ENV PATH /bifrost/src/:$PATH
ENTRYPOINT ["src/launcher.py"]
CMD ["src/launcher.py", "--help"]
#- Set up entry point:end --------------------------------------------------------------------------