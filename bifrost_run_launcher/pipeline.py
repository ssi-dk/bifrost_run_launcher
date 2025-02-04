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

os.umask(0o002)

def calculate_md5(sequence: str) -> str:
    md5_hash = hashlib.md5(sequence.encode('utf-8')).hexdigest()
    return md5_hash

def save_contigs_data(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"FASTA file not found at: {file_path}")

    print(f"file path is {file_path}")

    contig_lengths = []
    gc_contents = []
    date = datetime.now().strftime('%Y-%m-%d')

    with open(file_path, 'r') as fasta_file:
        for record in SeqIO.parse(fasta_file, "fasta"):
            contig_name = record.id  # Contig header
            print(f"{contig_name}")
            contig_seq = str(record.seq).replace("\n", "")  # Sequence without newlines
            #contig_data[contig_name] = contig_seq
            contig_length = len(contig_seq)
            gc_content = round((sum(contig_seq.count(x) for x in "GCgc") / contig_length) * 100, 2)
            contig_lengths.append(contig_length)
            gc_contents.append(gc_content)

            if verbose:
                print(f"Saving contig data for sample: {sample_name}, component: {component_name}, date {date}")
                print(f"Contig Name: {contig_name}")
                print(f"Length: {contig_length}")
                print(f"GC Content: {gc_content}%")
                #print(f"Sequence: {contig_seq[:10]}...")
                print("-" * 50)

    fasta_md5 = calculate_md5("".join(contig_data.values()))
    contig_no = len(contig_lengths)

    return fasta_md5,contig_no,contig_lengths,gc_contents,date

    #contigs["summary"]["md5"] = fasta_md5
    #contigs["summary"]["num_contigs"] = len(contig_lengths)
    #contigs["summary"]["total_length"] = contig_lengths
    #contigs["summary"]["gc_contents"] = gc_contents


def parse_directory(directory: str, file_name_list: List[Tuple[str,str]], run_metadata: pd.DataFrame, run_metadata_filename: str) -> Tuple[Dict, List[str]]:
    #print("parse_directory")
    #print(f"file name list is {file_name_list}")
    
    all_files: Set[str] = set(os.listdir(directory))
    #print(f"all files are : {all_files}")
    unused_files: Set[str] = all_files
    sample_dict = {}
    bifrost_mode = None #Either SEQ or ASM
    
    #define extensions for what is assumed to be unique to sequence reads and assemblies to differentiate in metadata
    seq_reads_ext = {".fq", ".fastq", ".fq.gz", ".fastq.gz"}
    asm_ext = {".fa", ".fasta", ".fa.gz", ".fasta.gz"}

    for sample_files in file_name_list:
        print(f"sample files: {sample_files}")
        #file_extensions = {os.path.splitext(f)[1].lower() for f in sample_files} # define as a set {} for issubset function below
        #print(f"file extensions are {file_extensions}")
        file_extensions = set()
        print(f"file extensions are {file_extensions}")
        base, ext = os.path.splitext(sample_files[0])  # Extract first extension
        print(f"base is {base} and ext {ext}")
        if ext == ".gz":  # Handle double extensions like .fastq.gz
            base, ext = os.path.splitext(base)  # Extract real file type before .gz
            file_extensions.add(ext.lower())  # Normalize to lowercase
        else:
            file_extensions.add(ext.lower())
        print(f"Extracted file extensions: {file_extensions}")
        
        # checking if sequence reads
        if file_extensions.issubset(seq_reads_ext):
            print("inside sequence reads module")
            # For paired-end sequence read files - ensure exactly two files exist
            if len(sample_files) != 2:
                raise ValueError(f"Error: Sample {sample_files} must have exactly two read files.")
            bifrost_mode = "SEQ"

        # checking if it is assembly
        elif file_extensions.issubset(asm_ext):
            print("inside assembly module")
            # Assembly files - ensure exactly one file exists
            if len(sample_files) != 1:
                raise ValueError(f"Error: Sample {sample_files} must have exactly one assembly file.")
            bifrost_mode = "ASM"    
        
        print(f"the bifrost launching mode is {bifrost_mode}")

        if all_files.issuperset(sample_files):
            unused_files.difference_update(sample_files)
            sample_name = run_metadata.loc[lambda df: df["filenames"] == sample_files, "sample_name"]
            for n in sample_name:
                sample_dict[n] = list(sample_files)
    
    unused_files.discard(run_metadata_filename)
    
    if bifrost_mode is None:
        raise ValueError("Unable to create run_script for pipeline initiation due to no valid sequencing or assembly files detected.")

    return (sample_dict,bifrost_mode,list(unused_files))

def format_metadata(run_metadata: TextIO, rename_column_file: TextIO = None) -> pd.DataFrame:
    df = None

    try:
        df = pd.read_table(run_metadata)
        #print("\n[DEBUG] Raw metadata before processing:")
        #print(df.to_string()) 

        # Rename columns if a colmap json mapping file is provided
        if rename_column_file is not None:
            with open(rename_column_file, "r") as rename_file:
                df = df.rename(columns=json.load(rename_file))
                print("\n[DEBUG] Columns renamed with colmap json to:", df.columns.tolist())
        else:
            expected_columns = ["sample_name", "species", "institution", "lab", "project", "date", "full_id", "filenames", "read_type", "purpose"]
            if len(df.columns) == len(expected_columns):
                df.columns = expected_columns
                print("\n[DEBUG] Columns renamed with expected file name to:", df.columns.tolist())

        # Drop unnamed columns (e.g., empty trailing columns from Excel)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        #print("\n[DEBUG] after unamed columns:")
        #print(df.to_string())
    
        # Drop rows with missing `sample_name` or `filenames`
        df = df.dropna(subset=["sample_name", "filenames"])
        #print("\n[DEBUG] after dropped names:")
        #print(df.to_string())

        # Save original `sample_name` before cleaning
        df["temp_sample_name"] = df["sample_name"]

        # Clean sample names
        df["sample_name"] = df["sample_name"].astype(str).str.strip()
        df["sample_name"] = df["sample_name"].str.replace(r"[^a-zA-Z0-9-_]", "_", regex=True)
        #print("\n[DEBUG] after clean names:")
        #print(df.to_string())

        # Track changed and duplicated sample names
        df["changed_sample_names"] = df["sample_name"] != df["temp_sample_name"]
        df["duplicated_sample_names"] = df["sample_name"].duplicated(keep="first")
        #print("\n[DEBUG] after duplicated names:")
        #print(df.to_string())

        # Convert filenames from a string to a tuple
        df["filenames"] = df["filenames"].apply(lambda x: tuple(x.strip().split('/')))
        #print("\n[DEBUG] after tuple names:")
        #print(df.to_string())

        # Initialize tracking columns
        df["haveReads"] = False
        df["haveAsm"] = False
        df["haveMetaData"] = True
        #print("\n[DEBUG] final:")
        #print(df.to_string())
        
        return df
    
    except Exception as e:
        print(traceback.format_exc())
        raise Exception("Error processing metadata file") from e

def get_sample_names(metadata: pd.DataFrame) -> List["str"]:
    return list(set(metadata["sample_name"].tolist()))

def get_file_pairs(metadata: pd.DataFrame) -> List[Tuple[str,str]]:
    return list(set(metadata["filenames"].tolist()))


def initialize_run(run: Run, samples: List[Sample], component: Component, 
                   input_folder: str, run_metadata: str, run_type: str, 
                   rename_column_file: str = None, component_subset: str = "ccc,aaa,bbb") -> Tuple[Run, List[Sample]]:
    print("Inside initialize run")
    
    print(f"before metadata format {run_metadata} with column file {rename_column_file}")
    metadata = format_metadata(run_metadata, rename_column_file)
    print("finished metadata")
    file_names_in_metadata = get_file_pairs(metadata)

    sample_dict,detected_bifrost_type,unused_files = parse_directory(input_folder, file_names_in_metadata, metadata, run_metadata)
    
    if run_type is None:
        run_type = detected_bifrost_type
        
    run_reference = run.to_reference()
    sample_list: List(Sample) = []
    

    if run_type == "ASM":
        #get_ASM_data
        fasta_md5,contig_no,contig_lengths,gc_contents,date = save_contigs_data(os.path.abspath(os.path.join(input_folder, sample_dict[sample_name][0])))

    for sample_name in sample_dict:
        #metadata.loc[metadata["sample_name"] == sample_name, "haveMetaData"] = True
        #metadata.loc[metadata["sample_name"] == sample_name, "hasData"] = True
        
        sample = Sample(name=run.sample_name_generator(sample_name))
        sample["run"] = run_reference
        sample["display_name"] = sample_name
        sample_exists = False
        
        for i in range(len(samples)):
            if samples[i]["name"] == sample_name:
                print(f"Sample {sample_name} exists")
                sample_exists = True
                sample = samples[i]
            
        if run_type == "SEQ":
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
            print(paired_reads)
            sample.set_category(paired_reads)
        elif run_type == "ASM":
            contigs = Category(value={
                "name": "assembly",
                "component": {"id": component["_id"], "name": component["name"]},
                "summary": {
                    "data": [os.path.abspath(os.path.join(input_folder, sample_dict[sample_name][0]))],
                    "md5":fasta_md5,
                    "num_contigs":contig_no,
                    "total_length":contig_lengths,
                    "gc_contents":gc_contents,
                    "date_added":date                   
                },
                "report": {}
            })
            sample.set_category(contigs)

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
        except DuplicateKeyError:
            print(f"Sample {sample_name} exists - reusing")
        
        sample_list.append(sample)
    
    run['component_subset'] = component_subset # this might just be for annotating in the db
    run["type"] = run_type
    run["path"] = os.getcwd()
    print(f"THE RUN TYPE FOR ISSUES ARE {run_type}")
    print(run["type"])

    if run["type"] == "SEQ":
        run["issues"] = {
            "duplicated_samples": list(metadata[metadata['duplicated_sample_names'] == True]['sample_name']),
            "changed_sample_names": list(metadata[metadata['changed_sample_names'] == True]['sample_name']),
            "unused_files": unused_files,
            "samples_without_reads": list(metadata[metadata['haveReads'] == False]['sample_name']),
            "samples_without_metadata": list(metadata[metadata['haveMetaData'] == False]['sample_name']),
        }
    elif run["type"] == "ASM":
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

    return (run, sample_list)


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
    script = ""
    if pre_script_location != None:
        with open(pre_script_location, "r") as pre_script_file:
            pre_script = pre_script_file.read()
            script = script + replace_run_info_in_script(pre_script, run)

    if per_sample_script_location != None:
        with open(per_sample_script_location, "r") as per_sample_script_file:
            per_sample_script = per_sample_script_file.read()
        per_sample_script = replace_run_info_in_script(per_sample_script, run)
        for sample in samples:
            script = script + replace_sample_info_in_script(per_sample_script, sample)

    if post_script_location != None:
        with open(post_script_location, "r") as post_script_file:
            post_script = post_script_file.read()
        script = script + replace_run_info_in_script(post_script, run)

    return script

def run_pipeline(args: object) -> None:
    if not os.path.isdir(args.outdir):
        os.makedirs(args.outdir)
    os.chdir(args.outdir)

    run_reference = RunReference(_id = args.run_id, name = args.run_name)
    
    print(f"{run_reference.json = }")
    if args.re_run:
        run: Run = Run.load(run_reference)
        if run is None and args.run_id is not None: # mistyped id
            raise ValueError(f"_id={args.run_id} not in db.")
        elif run is None:
            run: Run = Run(name=args.run_name)
    else:
        run: Run = Run(name=args.run_name)
    samples: List[Sample] = []
    # Add existing samples from run.samples if they exist
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
        if args.debug:
            print(f"{run = }\n{samples = }")
        #run, samples = initialize_run(run=run, samples=samples, component=args.component, input_folder=args.reads_folder, run_metadata=args.run_metadata, run_type=args.run_type, rename_column_file=args.run_metadata_column_remap, component_subset=args.component_subset)
        run, samples = initialize_run(run=run, samples=samples, component=args.component, 
                                      input_folder=args.input_folder, run_metadata=args.run_metadata, 
                                      run_type=args.run_type, rename_column_file=args.run_metadata_column_remap,
                                      component_subset=args.component_subset)

        print(f"Run {run['name']} and samples added to DB")
    else:
        print(f"Reprocessing samples from run {run['name']}") # we only want to subset samples from a pre-existing run
        if args.sample_subset != None:
            sample_subset = set(args.sample_subset.split(","))
            sample_inds_to_keep = []
            if len(samples) >= 1:
                sample_names_orig = set([i['categories']['sample_info']['summary']['sample_name'] for i in samples])
                missentered_subset_samples = ",".join([str(i) for i in (sample_subset - sample_names_orig)])
                if len(missentered_subset_samples) > 0:
                    print(f"{missentered_subset_samples} not present in run.")
                for i,sample in enumerate(samples):
                    if sample['categories']['sample_info']['summary']['sample_name'] in sample_subset:
                        sample_inds_to_keep.append(i)
            samples = [samples[i] for i in sample_inds_to_keep]

    if args.debug:
        print("run")
        print(run)
        print("samples")
        print(samples)

    script = generate_run_script(
        run,
        samples,
        args.pre_script,
        args.per_sample_script,
        args.post_script)
    with open("run_script.sh", "w") as fh:
        fh.write(script)

    print("Done, to run execute bash run_script.sh")
 
#if __name__ == "__main__":
#     parse_args(sys.argv[1:])
#if __name__ == "__main__":
#    main()
