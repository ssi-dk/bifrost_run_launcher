#!/usr/bin/env python3
"""
Initialization program for paired end Illumina reads
"""
import re
import os
from sys import stderr
import traceback
import pandas as pd
import json
import sys
from bifrostlib.datahandling import RunReference
from bifrostlib.datahandling import Run
from bifrostlib.datahandling import Sample
from bifrostlib.datahandling import Category
from bifrostlib.datahandling import Component
import pprint
import pymongo
from typing import List, Set, Dict, TextIO, Pattern, Tuple
from pymongo.errors import DuplicateKeyError
import argparse
import hashlib
from datetime import datetime
from Bio import SeqIO
import logging
import subprocess

os.umask(0o002)


# Setup logging
def setup_logging(log_dir: str,script_name: str):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    script_basename = os.path.splitext(os.path.basename(script_name))[0]
    
    print("script basename: {basename}") 
    # Ensure log directory exists
    os.makedirs(log_dir, exist_ok=True)

    # Construct log file path correctly
    log_file = os.path.join(log_dir, f"bifrost_script_{script_basename}.log")

    print("log file {log_file}")

    # Get root logger
    logger = logging.getLogger()

    # Remove all handlers to reset logging to a new file
    while logger.hasHandlers():
        logger.removeHandler(logger.handlers[0])

    # Set up logging with a new file for each run
    logging.basicConfig(
        filename=log_file,
        filemode="a",  # Append mode
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )

    # Add console logging
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    logging.info(f"Logging started for {log_file}")

def calculate_md5(sequence: str) -> str:
    md5_hash = hashlib.md5(sequence.encode('utf-8')).hexdigest()
    return md5_hash

def calculate_md5_of_file(file_path: str) -> str:
    """Calculate the MD5 checksum of a file."""
    if not os.path.exists(file_path):
        logging.error(f"File {file_path} not found.")
        return None

    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    
    return hash_md5.hexdigest()

def save_contigs_data(file_path):
    if not os.path.exists(file_path):
        logging.error(f"FASTA file not found at: {file_path}")
        raise FileNotFoundError(f"FASTA file not found at: {file_path}")

    logging.info(f"Processing FASTA file: {file_path}")

    contig_data = {}
    contig_lengths = []
    gc_contents = []
    date = datetime.now().strftime('%Y-%m-%d')

    with open(file_path, 'r') as fasta_file:
        for record in SeqIO.parse(fasta_file, "fasta"):
            contig_name = record.id  # Contig header
            #print(f"{contig_name}")
            contig_seq = str(record.seq).replace("\n", "")  # Sequence without newlines
            contig_data[contig_name] = contig_seq
            contig_length = len(contig_seq)
            gc_content = round((sum(contig_seq.count(x) for x in "GCgc") / contig_length) * 100, 2)
            contig_lengths.append(contig_length)
            gc_contents.append(gc_content)

    fasta_md5 = calculate_md5("".join(contig_data.values()))
    contig_no = len(contig_lengths)

    logging.info(f"FASTA MD5: {fasta_md5}, Contigs: {contig_no}, Avg Length: {sum(contig_lengths)/len(contig_lengths) if contig_lengths else 0:.2f}")

    return fasta_md5,contig_no,contig_lengths,gc_contents,date

def parse_directory(directory: str, file_name_list: List[Tuple[str,str]], run_metadata: pd.DataFrame, run_metadata_filename: str) -> Tuple[Dict, List[str]]:
    all_files: Set[str] = set(os.listdir(directory))
    unused_files: Set[str] = all_files
    sample_dict = {}
    
    bifrost_mode = None #Either SEQ or ASM
    
    #define extensions for what is assumed to be unique to sequence reads and assemblies to differentiate in metadata
    seq_reads_ext = {".fq", ".fastq", ".fq.gz", ".fastq.gz"}
    asm_ext = {".fa", ".fasta", ".fa.gz", ".fasta.gz"}

    for sample_files in file_name_list:
        # Downstream it is assumed that there are exactly two sequence files, 
        # so we test and complain here if that is not the case.

        file_extensions = set()
        #print(f"file extensions are {file_extensions}")

        base, ext = os.path.splitext(sample_files[0])  # Extract first extension
        #print(f"base is {base} and ext {ext}")
        #logging.info(f"base is {base} and ext {ext}")

        if ext == ".gz":  # Handle double extensions like .fastq.gz
            base, ext = os.path.splitext(base)  # Extract real file type before .gz
            file_extensions.add(ext.lower())  # Normalize to lowercase
        else:
            file_extensions.add(ext.lower())
        
        # checking if sequence reads
        if file_extensions.issubset(seq_reads_ext):
            #print("inside sequence reads module")
            # For paired-end sequence read files - ensure exactly two files exist
            if len(sample_files) != 2:
                logging.error(f"Error: Sample {sample_files} must have exactly two read files.")
                raise ValueError(f"Error: Sample {sample_files} must have exactly two read files.")
            bifrost_mode = "SEQ"
        elif file_extensions.issubset(asm_ext):
            logging.info(f"Bifrost mode: {bifrost_mode}")
            if len(sample_files) != 1:
                logging.error(f"Error: Sample {sample_files} must have exactly one assembly file.")
                raise ValueError(f"Error: Sample {sample_files} must have exactly one assembly file.")
            bifrost_mode = "ASM"

        if all_files.issuperset(sample_files):
            unused_files.difference_update(sample_files)
            sample_name = run_metadata.loc[lambda df: df["filenames"] == sample_files, "sample_name"]
            for n in sample_name:
                sample_dict[n] = list(sample_files)

    if bifrost_mode is None:
        logging.error(f"Error: Unable to create run_script for pipeline initiation due to no valid sequencing or assembly files detected.")
        raise ValueError("Unable to create run_script for pipeline initiation due to no valid sequencing or assembly files detected.")

    logging.info(f"Bifrost mode: {bifrost_mode}")
    unused_files.discard(run_metadata_filename)
    return (sample_dict, list(unused_files), bifrost_mode)

def format_metadata(run_metadata: TextIO, rename_column_file: TextIO = None) -> pd.DataFrame:
    df = None

    try:
        df = pd.read_table(run_metadata)
        logging.info(f"Initial metadata loaded with {df.shape[0]} rows and {df.shape[1]} columns.")

        # Rename columns if a colmap json mapping file is provided
        if rename_column_file is not None:
            with open(rename_column_file, "r") as rename_file:
                df = df.rename(columns=json.load(rename_file))
                logging.info(f"Columns renamed using JSON mapping: {df.columns.tolist()}")
        else:
            expected_columns = ["sample_name", "species", "institution", "lab", "project", "date", "full_id", "filenames", "read_type", "purpose"]
            if len(df.columns) == len(expected_columns):
                df.columns = expected_columns
                logging.info("Columns renamed: {df.columns.tolist()} using expected default names: {expected_columns}.")

        # Drop unnamed columns (e.g., empty trailing columns from Excel)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]  
        # Drop rows with missing `sample_name` or `filenames`
        df = df.dropna(subset=["sample_name", "filenames"])
        logging.info(f"Metadata cleaned, remaining {df.shape[0]} rows.")

        # Save original `sample_name` before cleaning
        df["temp_sample_name"] = df["sample_name"]
        # Clean sample names
        df["sample_name"] = df["sample_name"].astype(str).str.strip()
        df["sample_name"] = df["sample_name"].str.replace(r"[^a-zA-Z0-9-_]", "_", regex=True)
        
        # Track changed and duplicated sample names
        df["changed_sample_names"] = df["sample_name"] != df["temp_sample_name"]
        df["duplicated_sample_names"] = df["sample_name"].duplicated(keep="first")
        
        # Convert filenames from a string to a tuple
        df["filenames"] = df["filenames"].apply(lambda x: tuple(x.strip().split('/')))
        
        # Initialize tracking columns
        df["haveReads"] = False
        df["haveAsm"] = False
        df["haveMetaData"] = True
        
        logging.info("Metadata formatted successfully.")
                
        return df
    
    except Exception as e:
        logging.error("Error formatting metadata: " + str(e))
        logging.error(traceback.format_exc())
        raise

def get_sample_names(metadata: pd.DataFrame) -> List["str"]:
    return list(set(metadata["sample_name"].tolist()))

def get_file_pairs(metadata: pd.DataFrame) -> List[Tuple[str,str]]:
    return list(set(metadata["filenames"].tolist()))

def initialize_run(run: Run, samples: List[Sample], component: Component, input_folder: str = ".",
                   run_metadata: str = "run_metadata.txt", rename_column_file: str = None,
                   #regex_pattern: str = r"^(?P<sample_name>[a-zA-Z0-9_\-]+?)(_S[0-9]+)?(_L[0-9]+)?_(R?)(?P<paired_read_number>[1|2])(_[0-9]+)?(\.fastq\.gz)$",
                   component_subset: str = "ccc,aaa,bbb"
                   ) -> Tuple[Run, List[Sample], str]:

    logging.info(f"Initializing run: {run['name']} with {len(samples)} samples")

    metadata = format_metadata(run_metadata, rename_column_file)
    file_names_in_metadata = get_file_pairs(metadata)
    sample_dict, unused_files, run_mode = parse_directory(input_folder, file_names_in_metadata, metadata, run_metadata)
    
    run["type"] = "assembly" if run_mode == "ASM" else "sequencing"

    run_reference = run.to_reference()
    sample_list: List(Sample) = []
    
    for sample_name in sample_dict:
        logging.info(f"Processing sample: {sample_name}")

        metadata.loc[metadata["sample_name"] == sample_name, "haveMetaData"] = True
        metadata.loc[metadata["sample_name"] == sample_name, "haveReads"] = True

        sample = Sample(name=run.sample_name_generator(sample_name))
        sample["run"] = run_reference
        sample["display_name"] = sample_name
        sample_exists = False

        for i in range(len(samples)):
            if samples[i]["name"] == sample_name:
                logging.info(f"Sample {sample_name} already exists, reusing.")
                sample_exists = True
                sample = samples[i]
        
        if run_mode == "SEQ":
            paired_reads = Category(value={
                "name": "paired_reads",
                "component": {"id": component["_id"], "name": component["name"]}, # giving paired reads component id?
                "summary": {
                    "data": [
                        os.path.abspath(os.path.join(input_folder, sample_dict[sample_name][0])),
                        os.path.abspath(os.path.join(input_folder, sample_dict[sample_name][1]))
                    ]
                }
            })
            sample.set_category(paired_reads)
        
        elif run_mode == "ASM":
            fasta_md5,contig_no,contig_lengths,gc_contents,date = save_contigs_data(os.path.abspath(os.path.join(input_folder, sample_dict[sample_name][0])))
            
            assembly = Category(value={
                "name": "assembly",
                "component": {"id": component["_id"], "name": component["name"]},
                "summary": {
                    "data": [
                        os.path.abspath(os.path.join(input_folder, sample_dict[sample_name][0]))
                    ],
                    "md5":fasta_md5,
                    "num_contigs":contig_no,
                    "total_length":contig_lengths,
                    "gc_contents":gc_contents,
                    "date_added":date
                },
                "report": {}
            })
            sample.set_category(assembly)

        # consider if report {} is necessary

        #sample_metadata = json.loads(metadata.iloc[metadata[metadata["sample_name"] == sample_name].index[0]].to_json())
        sample_metadata = metadata.loc[metadata['sample_name'] == sample_name].to_dict(orient = 'records')[0] # more stable to missing fields
        sample_metadata['filenames'] = list(sample_metadata['filenames']) # changing from tuple to list to match original
        sample_info = Category(value={
            "name": "sample_info",
            "component": {"id": component["_id"], "name": component["name"]},
            "summary": sample_metadata
        })

        sample.set_category(sample_info)
        try:
            sample.save()
            logging.info(f"Sample {sample_name} saved successfully.")
        except DuplicateKeyError:
            logging.warning(f"Duplicate Sample {sample_name} found. Skipping save.")

        sample_list.append(sample)

    run['component_subset'] = component_subset # this might just be for annotating in the db
    
    run["path"] = os.getcwd()

    
    if run_mode == "SEQ":
        run["issues"] = {
            "duplicated_samples": list(metadata[metadata['duplicated_sample_names'] == True]['sample_name']),
            "changed_sample_names": list(metadata[metadata['changed_sample_names'] == True]['sample_name']),
            "unused_files": unused_files,
            "samples_without_reads": list(metadata[metadata['haveReads'] == False]['sample_name']),
            "samples_without_metadata": list(metadata[metadata['haveMetaData'] == False]['sample_name']),
        }
    elif run_mode == "ASM":
        run["issues"] = {
            "duplicated_samples": list(metadata[metadata['duplicated_sample_names'] == True]['sample_name']),
            "changed_sample_names": list(metadata[metadata['changed_sample_names'] == True]['sample_name']),
            "unused_files": unused_files,
            "samples_without_assembly": list(metadata[metadata['haveAsm'] == False]['sample_name']),
            "samples_without_metadata": list(metadata[metadata['haveMetaData'] == False]['sample_name']),
        }

    run.samples = [i.to_reference() for i in sample_list]
    run.save()

    with open("run.yaml", "w") as fh:
        fh.write(pprint.pformat(run.json))
    with open("samples.yaml", "w") as fh:
        for sample in sample_list:
            fh.write(pprint.pformat(sample.json))

    logging.info(f"Run {run['name']} initialized with {len(sample_list)} samples.")
    return (run, sample_list, run_mode)

def replace_run_info_in_script(script: str, run: object) -> str:
    positions_to_replace = re.findall(re.compile(r"\$run.[a-zA-Z]+_*[a-zA-Z]+"), script)
    for item in positions_to_replace:
        (key, value) = (item.split("."))
        script = script.replace(item, run[value])
    return script

def replace_sample_info_in_script(script: str, sample: object) -> str:
    positions_to_replace = re.findall(re.compile(r"\$sample\.[\.\[\]_a-zA-Z0-9]+"), script)
    for item in positions_to_replace:
        (item.split(".")[1:])
        level = sample.json
        for value in item.split(".")[1:]:
            if value.endswith("]"):
                (array_item, index) = value.split("[")
                index = int(index[:-1])
                level = level[array_item][index]
            elif value.endswith("id"):
                level = level[value]['$oid'] # {oid: <mongodb_id>}
            else:
                level = level[value]
        if(level is not None):
            if not isinstance(level, str):
                level = str(level)
            script = script.replace(item, level)
    return script

def generate_run_script(run: Run, samples: Sample, pre_script_location: str, per_sample_script_location: str, post_script_location: str) -> str:
    logging.info(f"Generating run script for {run['name']}")
    
    script = ""
    
    if pre_script_location != None:
        with open(pre_script_location, "r") as pre_script_file:
            logging.info(f"Reading pre-run script from {pre_script_location}")
            pre_script = pre_script_file.read()
            script = script + replace_run_info_in_script(pre_script, run)

    if per_sample_script_location != None:
        logging.info(f"Reading per-sample script from {per_sample_script_location}")
        with open(per_sample_script_location, "r") as per_sample_script_file:
            per_sample_script = per_sample_script_file.read()
   
        per_sample_script = replace_run_info_in_script(per_sample_script, run)

        for sample in samples:
            script = script + replace_sample_info_in_script(per_sample_script, sample)

    if post_script_location != None:
        logging.info(f"Reading post-run script from {post_script_location}")
        with open(post_script_location, "r") as post_script_file:
            post_script = post_script_file.read()
            
        script = script + replace_run_info_in_script(post_script, run)
    
    logging.info(f"Run script generated successfully: {len(script)} characters")
    return script

def run_pipeline(args: object) -> None:
    #setup_logging(log_dir="logs", script_name=__file__)  # logging is initialized
    
    os.chdir(args.outdir)
    
    tmp_folder = os.getcwd()
    setup_logging(tmp_folder,os.path.basename(__file__))
    run_reference = RunReference(_id = args.run_id, name = args.run_name)
    logging.info(f"Running reference with args id: {args.run_id} and args run name: {args.run_name}")

    if args.re_run:
        logging.info("Re-run detected. Attempting to load existing run.")
        run: Run = Run.load(run_reference)

        if run is None and args.run_id is not None: # mistyped id
            logging.error(f"Run ID {args.run_id} not found in database.")
            raise ValueError(f"_id={args.run_id} not in db.")
        
        if run is None:
            logging.info(f"No existing run found, creating new run: {args.run_name}")
            run: Run = Run(name=args.run_name)
    else:
        logging.info(f"Creating new run: {args.run_name}")
        run: Run = Run(name=args.run_name)

    samples: List[Sample] = []
    for sample_reference in run.samples:
        sample = Sample.load(sample_reference)
        if sample is not None:
            samples.append(sample)

    # check if the run has an id and whether it exists in the db
    client = pymongo.MongoClient(os.environ['BIFROST_DB_KEY'])
    db = client.get_database()
    runs = db.runs
    run_name_matches = [str(i["_id"]) for i in runs.find({"name":run['name']})]

    if "_id" not in run.json or args.sample_subset is None:
        logging.info(f"Initializing new run: {run['name']}")
        run, samples, run_mode = initialize_run(run=run, samples=samples, component=args.component, 
                                      input_folder=args.reads_folder, run_metadata=args.run_metadata, 
                                      rename_column_file=args.run_metadata_column_remap, 
                                      component_subset=args.component_subset)
        logging.info(f"Run {run['name']} initialized successfully.")
    else:
        logging.info(f"Reprocessing selected samples for run: {run['name']}")
        
        if args.sample_subset != None:
            sample_subset = set(args.sample_subset.split(","))
            sample_inds_to_keep = []
            
            if len(samples) >= 1:
                sample_names_orig = set([i['categories']['sample_info']['summary']['sample_name'] for i in samples])
                missentered_subset_samples = ",".join([str(i) for i in (sample_subset - sample_names_orig)])
                
                if len(missentered_subset_samples) > 0:
                    logging.warning(f"Missing samples in the subset {missentered_subset_samples}")
                    
                for i,sample in enumerate(samples):
                    if sample['categories']['sample_info']['summary']['sample_name'] in sample_subset:
                        sample_inds_to_keep.append(i)
            
            samples = [samples[i] for i in sample_inds_to_keep]

    logging.info("Generating run script.")
    
    if run_mode == "SEQ":
        script = generate_run_script(
            run,
            samples,
            args.pre_script,
            args.per_sample_script,
            args.post_script)

    # for now try with the same scripts, but make placeholder for additional pre,per and post
    if run_mode == "ASM":
        script = generate_run_script(
            run,
            samples,
            args.pre_script,
            args.per_sample_script,
            args.post_script)
    
    with open("run_script.sh", "w") as fh:
        fh.write(script)
    
    # Compute MD5 checksum of the script
    script_md5 = calculate_md5_of_file("run_script.sh")
    logging.info(f"MD5 checksum of run_script.sh: {script_md5}")

    print("Done, {args.outdir}")
    print("Done, to run execute bash run_script.sh")

# if __name__ == "__main__":
#     parse_args(sys.argv[1:])
