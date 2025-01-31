
python3 launcher.py --run_metadata sofi_metadata.tsv --reads_folder ../tests/test_reads/ --run_name 1910M50353_Campy_end2end_test -pre pre.sh -per per.sh -post post.sh --re_run --debug

python3 launcher.py --run_metadata sofi_metadata.tsv --reads_folder /home/people/rashen/bifrost_run_launcher/bifrost_run_launcher --run_name 1910M50353 -pre pre_asm.sh -per per_asm.sh -post post.sh --run_type ASM --re_run

(bifrost_dev_run_launcher_v2.3.0) [rashen@g-05-c0359 bifrost_run_launcher]$ python3 -c "import bifrost_run_launcher.pipeline as p; print(p.__file__)"
/home/projects/fvst_ssi_dtu/apps/sofi_bifrost_dev/scripts/bifrost/components/bifrost_run_launcher/bifrost_run_launcher/pipeline.py

(bifrost_dev_run_launcher_v2.3.0) [rashen@g-05-c0359 bifrost_run_launcher]$ md5sum run_script.sh
4f43b66c458196f1b0a2c63aa407d143  run_script.sh

# this would be the output of metadat
ysample_name      provided_species institution group     experiment_name sequence_run_date                   sofi_sequence_id                                                                   filenames  project_no project_title temp_sample_name  changed_sample_names  duplicated_sample_names  haveReads  haveMetaData
0  1910M50353  Campylobacter jejuni         SSI   FBI  Campy_end2end_test        2024-10-22  1910M50353_Campy_end2end_test_SSI  (1910M50353_S34_L555_R1_001.fastq.gz, 1910M50353_S34_L555_R2_001.fastq.gz)           1  Surveillance       1910M50353                 False                    False      False          True
Sample 1910M50353 exists - reusing
Run 1910M50353_Campy_end2end_test and samples added to DB

