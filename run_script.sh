# Pre-script example
echo "start pre_script test_run test";
echo "end pre_script";
# Per sample script example
echo "Running Sample1 from test_run";
BIFROST_RAW_DATA_MNT="/raw_data/mnt";
BIFROST_PIPELINE_TOOLS="/tools/singularity";
mkdir Sample1;
cd Sample1;
singularity run -B \
$BIFROST_RAW_DATA_MNT,\
/tmp/pytest-of-root/pytest-1/test_pipeline0/samples/Sample1_R1.fastq.gz,\
/tmp/pytest-of-root/pytest-1/test_pipeline0/samples/Sample1_R2.fastq.gz \
$BIFROST_PIPELINE_TOOLS/bifrost-min_read_check_2.0.7.sif \
-id 5f23bb00c85031a222cc696f;
singularity run -B \
$BIFROST_RAW_DATA_MNT,\
/tmp/pytest-of-root/pytest-1/test_pipeline0/samples/Sample1_R1.fastq.gz,\
/tmp/pytest-of-root/pytest-1/test_pipeline0/samples/Sample1_R2.fastq.gz \
$BIFROST_PIPELINE_TOOLS/bifrost-whats_my_species_2.0.7.sif \
-id 5f23bb00c85031a222cc696f;
singularity run -B \
$BIFROST_RAW_DATA_MNT,\
/tmp/pytest-of-root/pytest-1/test_pipeline0/samples/Sample1_R1.fastq.gz,\
/tmp/pytest-of-root/pytest-1/test_pipeline0/samples/Sample1_R2.fastq.gz \
$BIFROST_PIPELINE_TOOLS/bifrost-assemblatron_2.0.7.sif \
-id 5f23bb00c85031a222cc696f;
cd ..;
echo "Done Sample1 from test_run";
# Post-script example
echo "start post_script test_run test";
echo "end post_script";
