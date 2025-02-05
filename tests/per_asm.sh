
# Per sample script example
echo "Running $sample.name from $run.name";

SAMPLE=$sample.name;

mkdir $SAMPLE;
pushd $SAMPLE;

# First job is dependant on start, second job on first job and so on
SAMPLE_PIPELINE_ID=$BIFROST_SAMPLE_START_ID
for PIPELINE in $BIFROST_COMPONENTS_ASM
do
    echo "SAMPLE_PIPELINE_ID: $SAMPLE_PIPELINE_ID"
    if string_contains $PIPELINE $SINGULARITY_COMPONENTS; then
	SAMPLE_PIPELINE_ID=$(submit_sample_component_to_singularity $SAMPLE $PIPELINE $SAMPLE_PIPELINE_ID $sample.name $sample.categories.assembly.summary.data[0]);
    else
	SAMPLE_PIPELINE_ID=$(submit_sample_component $SAMPLE $PIPELINE $SAMPLE_PIPELINE_ID $sample.name);
    fi
done;
popd;
# Add last job id to the list.
BIFROST_SAMPLE_JOB_IDS=$BIFROST_SAMPLE_JOB_IDS:$SAMPLE_PIPELINE_ID;
echo "BIFROST_SAMPLE_JOB_IDS: $BIFROST_SAMPLE_JOB_IDS"
