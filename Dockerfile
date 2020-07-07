# This is intended to run in Github Actions
FROM continuumio/miniconda3:4.7.10

ARG name="bifrost-run_launcher"
ARG code_version
ARG resource_version
ARG environment

LABEL \
    name=${name} \
    description="Docker environment for ${name}" \
    code_version="${code_version}" \
    resource_version="${resource_version}" \
    environment="${environment}" \
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
    if [ "${environment}" = "dev" ] \
    then \
        pip install pytest; \
        pip install pytest-cov; \
        pip install pytest-profiling; \
        pip install coverage; \
    else \
        echo ${environment} \
    fi \
    sed -i'' 's/<code_version>/'"${code_version}"'/g' /bifrost/src/config.yaml; \
    sed -i'' 's/<resource_version>/'"${resource_version}"'/g' /bifrost/src/config.yaml;
#- Source code:end ---------------------------------------------------------------------------------

#- Set up entry point:start ------------------------------------------------------------------------
ENV PATH /bifrost/src/:$PATH
ENTRYPOINT ["/bifrost/src/launcher.py"]
CMD ["/bifrost/src/launcher.py", "--help"]
#- Set up entry point:end --------------------------------------------------------------------------