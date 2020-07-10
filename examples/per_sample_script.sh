# Per sample script example
echo "Running $sample.name from $run.name";
BIFROST_RAW_DATA_MNT="/raw_data/mnt";
BIFROST_PIPELINE_TOOLS="/tools/singularity";
mkdir $sample.name;
cd $sample.name;
singularity run -B \
$BIFROST_RAW_DATA_MNT,\
$sample.properties.paired_reads.summary.data[0],\
$sample.properties.paired_reads.summary.data[1] \
$BIFROST_PIPELINE_TOOLS/bifrost-min_read_check_2.0.7.sif \
-id $sample._id;
singularity run -B \
$BIFROST_RAW_DATA_MNT,\
$sample.properties.paired_reads.summary.data[0],\
$sample.properties.paired_reads.summary.data[1] \
$BIFROST_PIPELINE_TOOLS/bifrost-whats_my_species_2.0.7.sif \
-id $sample._id;
singularity run -B \
$BIFROST_RAW_DATA_MNT,\
$sample.properties.paired_reads.summary.data[0],\
$sample.properties.paired_reads.summary.data[1] \
$BIFROST_PIPELINE_TOOLS/bifrost-assemblatron_2.0.7.sif \
-id $sample._id;
cd ..;
echo "Done $sample.name from $run.name";
