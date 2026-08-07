# bifrost_run_launcher

This module is run given a directory of reads or assemblies and a metadata.tsv which provides samples expected and 
provided species. The script will then create a sample object for all samples found and a run object 
containing all the sample objects. Moreover, sample_component objects are initialized for each 
sample - component combination, to keep tabs on component statuses. A script is then created based of
the provided pre, per, and post scripts that can are customized to each install. Running this script 
will run the pipeline: each sample will be ran against the provided components in the per script

## Requirements

- Input directory of sequencing reads [SEQ] or assemblies [ASM]
- Metadata sheet as tab separated text file
- [Optional] json to re-name columns

## Run script

Initialize:
```
python -m bifrost_run_launcher \
        -rerun \
        -pre bifrost_impl_sofi/scripts/launcher_scripts/pre.sh \
        -per bifrost_impl_sofi/scripts/launcher_scripts/per_asm.sh \
        -post bifrost_impl_sofi/scripts/launcher_scripts/post.sh \
        -colmap bifrost_impl_sofi/settings/colmap.json \
        -reads $BIFROST_RUN_DIR/samples \
        -meta $BIFROST_RUN_DIR/sofi_metadata.clean.tsv \
        -name $BIFROST_RUN_NAME \
        -out $BIFROST_RUN_DIR \
        --run_type "run" \
        --run_mode "SEQ"
```

Re-run sample and component(s) already in database:
```
python -m bifrost_run_launcher \
        -rerun \
        --sample_subset SAMPLE_ID \
        --outdir $BIFROST_RUN_DIR \
        --run_mode "SEQ" \
        --component_subset bifrost_min_read_check_v2.2.10,bifrost_whats_my_species_v2.2.12 \
        --re_run_components
```

Finish:
```
python -m bifrost_run_launcher \
        --re_run \
        --sample_subset SAMPLE_ID \
        --outdir $BIFROST_RUN_DIR \
        --run_mode "SEQ" \
        --component_subset bifrost_min_read_check_v2.2.10,bifrost_whats_my_species_v2.2.12 \
        --finish
```

## Usage

```
usage: python -m bifrost_run_launcher [-h] [--debug] [-out OUTDIR] [-pre PRE_SCRIPT] [-per PER_SAMPLE_SCRIPT] [-post POST_SCRIPT]
                                      [-meta RUN_METADATA] [-reads READS_FOLDER] [-name RUN_NAME] [-type RUN_TYPE] [-m RUN_MODE]
                                      [-colmap RUN_METADATA_COLUMN_REMAP] [-id RUN_ID] [-recomp] [-rerun] [-co COMPONENT_SUBSET]
                                      [-s SAMPLE_SUBSET] [-f]

-Description------------------------------------
Processes a folder for running in bifrost
------------------------------------------------

-Environmental Variables/Defaults---------------
BIFROST_CONFIG_DIR: scripts
BIFROST_RUN_DIR: .
------------------------------------------------

options:
  -h, --help            show this help message and exit
  --debug               Show arg values
  -out, --outdir OUTDIR
                        Output directory
  -pre, --pre_script PRE_SCRIPT
                        Pre script template run before sample script
  -per, --per_sample_script PER_SAMPLE_SCRIPT
                        Per sample script template run on each sample
  -post, --post_script POST_SCRIPT
                        Post script template run after sample script
  -meta, --run_metadata RUN_METADATA
                        Run metadata tsv
  -reads, --reads_folder READS_FOLDER
                        Run reads folder
  -name, --run_name RUN_NAME
                        Run name, if not provided it will default to current folder name
  -type, --run_type RUN_TYPE
                        Run type for metadata organization [run, events]
  -m, --run_mode RUN_MODE
                        Run mode for pipeline selection [SEQ, ASM]
  -colmap, --run_metadata_column_remap RUN_METADATA_COLUMN_REMAP
                        Remaps metadata tsv columns to bifrost values
  -id, --run_id RUN_ID  For re-running a run
  -recomp, --re_run_components
                        For re-initializing a subset of sample components for sample(s)
  -rerun, --re_run      For re-running a run
  -co, --component_subset COMPONENT_SUBSET
                        Component subset to run on samples. Use a comma for separation:
                        bifrost_min_read_check_v2.2.10,bifrost_whats_my_species_v2.2.12,bifrost_assemblatron_v2.3.3
  -s, --sample_subset SAMPLE_SUBSET
                        Sample subset to process, None will run all samples. Short names, use a comma for separation
  -f, --finish          Finalize statuses for sample components for sample(s) in run
```
