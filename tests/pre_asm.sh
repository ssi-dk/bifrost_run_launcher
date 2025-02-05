
	# KMA specific config

# Utility functions
string_contains() {
  local search="$1"
  local string="$2"

  for element in $string; do
    if [[ "$element" == "$search" ]]; then
      return 0
    fi
  done

  return 1
}

# Error handling
handle_error() {
  local command="$BASH_COMMAND"
  echo "An error occurred while executing: $command"
  exit 1
}

# Set the trap to call the exception handling function
trap 'handle_error' ERR

submit_sample_component_to_singularity() {
  local SAMPLE="$1"
  local COMPONENT="$2"
  local PREVIOUS_ID="$3"
  local sample_name="$4"
  local asm="$5"

  local command="\
      module load tools; \
      module load "$SINGULARITY_VERSION"; \
      export BIFROST_DB_KEY="$BIFROST_DB_KEY"; \
      export ENTEROBASE_SERVER="$ENTEROBASE_SERVER"; \
      export ENTEROBASE_USERNAME="$ENTEROBASE_USERNAME"; \
      export ENTEROBASE_PASSWORD="$ENTEROBASE_PASSWORD"; \
      hostname; \
      singularity run -B \
        \"$PWD,\
        $BIFROST_ASM_DATA_MNT,\
        $asm,\
        /scratch\" \
        $BIFROST_PIPELINE_TOOLS/$COMPONENT \
        -name $sample_name"

  SAMPLE_PIPELINE_ID=$(\
    echo $command | \
    qsub \
      -d $PWD \
      -A $BIFROST_JOB_ACCOUNT \
      -W depend=afterany:$PREVIOUS_ID \
      -W umask=002 \
      -N "${SAMPLE}_${PIPELINE}_bf" \
      -W x=advres:$BIFROST_RESNODES \
      -l nodes=1:ppn=$BIFROST_JOB_CPUS,mem=$BIFROST_JOB_MEM,walltime=$BIFROST_JOB_TIME \
    );
  echo $SAMPLE_PIPELINE_ID
}

submit_sample_component() {
  local SAMPLE="$1"
  local COMPONENT="$2"
  local PREVIOUS_ID="$3"
  local sample_name="$4"

  local COMPONENT_VERSION=v${COMPONENT##*_v}
  local COMPONENT_NAME=${COMPONENT%_v*}
  local COMPONENT_CLEAN_NAME=${COMPONENT_NAME#bifrost_}
  local STAGE=${BIFROST_STAGE:+${BIFROST_STAGE}_}

  local CONDA_ENV_NAME=bifrost_${STAGE}${COMPONENT_CLEAN_NAME}_${COMPONENT_VERSION}

  local command=$(echo 'module load tools;' \
                'module load '$CONDA_VERSION';' \
                'eval "$(conda shell.bash hook)";' \
                'conda activate "'$CONDA_ENV_NAME'";' \
                'python -m "'$COMPONENT_NAME'" --sample_name "'$sample_name'" ;')
  echo $command > command.txt
  SAMPLE_PIPELINE_ID=$(\
    echo $command | \
    qsub \
      -v $QSUB_KEEP_VARS \
      -d $PWD \
      -A $BIFROST_JOB_ACCOUNT \
      -W depend=afterany:$PREVIOUS_ID \
      -W umask=002 \
      -N "${SAMPLE}_${COMPONENT_NAME}_bf" \
      -W x=advres:$BIFROST_RESNODES \
      -l nodes=1:ppn=$BIFROST_JOB_CPUS,mem=$BIFROST_JOB_MEM,walltime=$BIFROST_JOB_TIME \
    );
  echo $SAMPLE_PIPELINE_ID
}

# General config
export BIFROST_PIPELINE_TOOLS="${BIFROST_PIPELINE_TOOLS:-$BIFROST_IMAGE_DIR}"
export BIFROST_OUTPUT_DIR="${BIFROST_OUTPUT_DIR:-.}"

# Running the following to get 1 id in SAMPLE_PIPELINE_ID for per sample script
unset BIFROST_SAMPLE_START_ID
unset BIFROST_SAMPLE_JOB_IDS
BIFROST_SAMPLE_START_ID=$(echo \
"echo Run started" | \
qsub \
-A $BIFROST_JOB_ACCOUNT \
-h \
-N "bf_$run.name" \
-d $PWD \
-l nodes=1:ppn=1,mem=1gb,walltime=$BIFROST_JOB_TIME \
-W x=advres:$BIFROST_RESNODES \
-W umask=002
);
BIFROST_SAMPLE_JOB_IDS=$BIFROST_SAMPLE_START_ID
echo "BIFROST_SAMPLE_JOB_IDS: $BIFROST_SAMPLE_JOB_IDS"

