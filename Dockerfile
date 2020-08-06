# This is intended to run in Github Actions
# Arg can be set to dev for testing purposes
ARG BUILD_ENV="prod"
ARG NAME="bifrost_run_launcher"
ARG CODE_VERSION="unspecified"
ARG RESOURCE_VERSION="unspecified"

# For dev build include testing modules via pytest done on github and in development.
# Watchdog is included for docker development (intended method) and should preform auto testing 
# while working on *.py files
FROM continuumio/miniconda3:4.7.10 as build_dev
ONBUILD ARG NAME
ONBUILD COPY . /${NAME}
ONBUILD WORKDIR ${NAME}
ONBUILD RUN \
    sed -i'' 's/<code_version>/'"${CODE_VERSION}"'/g' ${NAME}/config.yaml; \
    sed -i'' 's/<resource_version>/'"${RESOURCE_VERSION}"'/g' ${NAME}/config.yaml; \
    pip install -r requirements.dev.txt;
# For getting data to test, since we use mount points examples will overwrite examples so we need 
# another folder to store the read data.
ONBUILD COPY examples test_resources
ONBUILD RUN \
    cd test_resources; \ 
    wget -O S1_R1.fastq.gz -q ftp://ftp.sra.ebi.ac.uk/vol1/run/ERR430/ERR4301030/S1.R1.fastq.gz; \
    wget -O S1_R2.fastq.gz -q ftp://ftp.sra.ebi.ac.uk/vol1/run/ERR430/ERR4301030/S1.R2.fastq.gz; 

FROM continuumio/miniconda3:4.7.10 as build_prod
ONBUILD ARG NAME
ONBUILD COPY ${NAME} /${NAME}/${NAME}
COPY setup.py /${NAME}/setup.py
COPY requirements.txt /${NAME}/requirements.txt
ONBUILD RUN \
    sed -i'' 's/<code_version>/'"${CODE_VERSION}"'/g' /${NAME}/${NAME}/config.yaml; \
    sed -i'' 's/<resource_version>/'"${RESOURCE_VERSION}"'/g' /${NAME}/${NAME}/config.yaml; \
    pip install -r /${NAME}/requirements.txt

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
# 
#- Source code:end ---------------------------------------------------------------------------------

#- Set up entry point:start ------------------------------------------------------------------------
ENTRYPOINT ["python3", "-m", "bifrost_run_launcher"]
CMD ["python3", "-m", "bifrost_run_launcher", "--help"]
#- Set up entry point:end --------------------------------------------------------------------------