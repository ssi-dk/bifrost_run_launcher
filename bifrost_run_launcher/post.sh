# Post-script example
# BIFROST_JOB_MEM is set in Prescript
# BIFROST_JOB_CPUS is set in Prescript 
# BIFROST_JOB_PARTITION is set in Prescript
# SAMPLE_JOB_IDS is set in Prescript

# BIFROST_INSTITUTION inherited from bifrost_launcher.sh

recipient_var=BIFROST_RECIPIENTS_$BIFROST_INSTITUTION

last_job_id=$(echo \
"\
touch complete.txt
 " | \
qsub \
-W x=advres:$BIFROST_RESNODES \
-W depend=afterany:$BIFROST_SAMPLE_JOB_IDS \
-W umask=002 \
-A $BIFROST_JOB_ACCOUNT \
-N "post_$run.name" \
-d $PWD \
-l nodes=1:ppn=$BIFROST_JOB_CPUS,mem=$BIFROST_JOB_MEM,walltime=$BIFROST_JOB_TIME \
-m e -M ${!recipient_var}\
)


qrls $BIFROST_SAMPLE_START_ID;

