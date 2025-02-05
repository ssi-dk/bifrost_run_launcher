# step 1 running launcing bifrost -> cleaning data 

./launch_bifrost_asm.sh ssi 2024 campy_end2end_test_blabla_long_name___1910M50353_asm 

# step 2 running launcher, using bifrost_run_launcer component to create run_script.sh which creates the python -m component --sample_name component

python3 launcher.py -rerun -pre pre_asm.sh -per per_asm.sh -post post.sh -colmap colmap.json 
	--assembly_folder campy_end2end_test_blabla_long_name___1910M50353_asm/samples -meta metadata.clean.tsv 
	-name campy_end2end_test_blabla_long_name___1910M50353_asm --run_type ASM -out campy_end2end_test_blabla_long_name___1910M50353_asm

