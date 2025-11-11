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
from Bio import SeqIO
from datetime import datetime

os.umask(0o002)

def calculate_n50(lengths: List[int]) -> int:
    if not lengths:
        return 0 
    lengths_sorted = sorted(lengths, reverse=True) #sort contigs longest>shortest
    
    n50 = 0
    half = sum(lengths_sorted) / 2
    
    for Length in lengths_sorted:
        n50  += Length
        if n50  >= half:
            return Length
    return 0

def save_contigs_data(file_path: str) -> Tuple[int, int, int, float]:
    if not os.path.exists(file_path):
        print(f"FASTA file not found at: {file_path}")
        raise FileNotFoundError(f"FASTA file not found at: {file_path}")
    
    contig_lengths: List[int] = []
    gc_contents: List[float] = []
    
    with open(file_path, 'r') as fasta_file:
        for record in SeqIO.parse(fasta_file, "fasta"):
            contig_seq = str(record.seq).replace("\n", "")  # Sequence without newlines
            contig_length = len(contig_seq)
            gc_content = round((sum(contig_seq.count(x) for x in "GCgc") / contig_length) * 100, 2)
            contig_lengths.append(contig_length)
            gc_contents.append(gc_content)

    print(f"Contigs: {len(contig_lengths)}, Avg Length: {sum(contig_lengths)/len(contig_lengths) if contig_lengths else 0:.2f}")

    # aggregate stats
    total_len = sum(contig_lengths)
    num_contigs = len(contig_lengths)
    n50 = calculate_n50(contig_lengths)
    mean_gc = round(sum(gc_contents) / num_contigs, 2) if num_contigs else 0.0
    
    return total_len,num_contigs,n50,mean_gc

def parse_directory(directory: str, 
                    file_name_list: List[Tuple[str,str]], 
                    run_metadata: pd.DataFrame, 
                    run_metadata_filename: str) -> Tuple[Dict, List[str], str]:
    
    all_files: Set[str] = set(os.listdir(directory))
    unused_files: Set[str] = set(all_files)
    sample_dict = {}
        
    bifrost_mode = None #Either SEQ or ASM
    
    #define extensions for what is assumed to be unique to sequence reads and assemblies to differentiate in metadata
    seq_reads_ext = {".fq", ".fastq", ".fq.gz", ".fastq.gz"}
    asm_ext = {".fa", ".fasta", ".fa.gz", ".fasta.gz", ".fas", ".fas.gz", ".fna", ".fna.gz"}

    for sample_files in file_name_list:
        # Downstream it is assumed that there are exactly two sequence files, 
        # so we test and complain here if that is not the case.

        file_extensions = set()
        base, ext = os.path.splitext(sample_files[0])  # Extract first extension
        
        if ext == ".gz":  # Handle double extensions like .fastq.gz
            base, ext = os.path.splitext(base)  # Extract real file type before .gz
            file_extensions.add(ext.lower())  # Normalize to lowercase
        else:
            file_extensions.add(ext.lower())

        # checking if sequence reads
        if file_extensions.issubset(seq_reads_ext):
            # For paired-end sequence read files - ensure exactly two files exist
            if len(sample_files) != 2:
                print("Sample files:\n"+"\n".join(sample_files),file=sys.stderr)
                raise ValueError(f"Error: Sample {sample_files} has {len(sample_files)} sequence files, it must have exactly two read files")
            bifrost_mode = "SEQ"
        elif file_extensions.issubset(asm_ext):
            if len(sample_files) != 1:
                raise ValueError(f"Error: Sample {sample_files} has {len(sample_files)} assembly files, it must have exactly one assembly file.")
            bifrost_mode = "ASM"

        if all_files.issuperset(sample_files):
            unused_files.difference_update(sample_files)
            sample_name = run_metadata.loc[lambda df: df["filenames"] == sample_files, "sample_name"]
            for n in sample_name:
                sample_dict[n] = list(sample_files)
    
    if bifrost_mode is None:
        raise ValueError("Unable to create run_script for pipeline initiation due to no valid sequencing or assembly files detected.")

    unused_files.discard(run_metadata_filename)
    return (sample_dict, list(unused_files), bifrost_mode)


def format_metadata(run_metadata: TextIO, 
                    rename_column_file: TextIO = None) -> pd.DataFrame:
    df = None

    try:
        df = pd.read_table(run_metadata)

        # Rename columns if a colmap json mapping file is provided - consider removing this in a future iteration
        if rename_column_file is not None:
            with open(rename_column_file, "r") as rename_file:
                df = df.rename(columns=json.load(rename_file))
        
        # Drop unnamed columns (e.g., empty trailing columns from Excel)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        
        
        samples_no_index = df[df["sample_name"].isna()].index # drop unnamed samples
        samples_no_files_index = df[df["filenames"].isnull()].index # drop samples missing reads
        idx_to_drop = samples_no_index.union(samples_no_files_index)
        missing_files = ", ".join([df["sample_name"].iloc[i] for i in samples_no_files_index])
        print(f"samples {missing_files} missing files.")
        df = df.drop(idx_to_drop)
        
        # Save original `sample_name` before cleaning
        df["temp_sample_name"] = df["sample_name"]
        # Clean sample names
        df["sample_name"] = df["sample_name"].astype(str).str.strip()
        df["sample_name"] = df["sample_name"].str.replace(r"[^a-zA-Z0-9-_]", "_", regex=True)
        
        # Track changed and duplicated sample names
        df["changed_sample_names"] = df['sample_name'] != df['temp_sample_name']
        df["duplicated_sample_names"] = df.duplicated(subset="sample_name", keep="first")

        # Convert filenames from a string to a tuple
        df["filenames"] = df["filenames"].apply(lambda x: tuple(x.strip().split('/')))

        # Initialize tracking columns
        df["haveReads"] = False
        df["haveAsm"] = False
        df["haveMetaData"] = True
        
        df = df.map(lambda x: None if pd.isna(x) else x) #consider since i have removed lambda also change to df = df.where(pd.notna(df), None)  -> Detect existing (non-missing) values. -> Replace values where the condition is False.
        return df
    except Exception as e:
        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            print(df, file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
        raise ValueError(f"Bad metadata and/or rename column file: {e}") from e

def get_sample_names(metadata: pd.DataFrame) -> List["str"]:
    return list(set(metadata["sample_name"].tolist()))

def get_file_pairs(metadata: pd.DataFrame) -> List[Tuple[str,str]]:
    return list(set(metadata["filenames"].tolist()))


def initialize_run(run: Run, 
                   samples: List[Sample], 
                   component: Component, 
                   input_folder: str = ".",
                   run_metadata: str = "run_metadata.txt", 
                   run_type: str = None, 
                   rename_column_file: str = None,
                   component_subset: str = "ccc,aaa,bbb"
                   ) -> Tuple[Run, List[Sample], str]:
    
    metadata = format_metadata(run_metadata, rename_column_file)
    file_names_in_metadata = get_file_pairs(metadata)
    sample_dict, unused_files, run_mode = parse_directory(input_folder, file_names_in_metadata, metadata, run_metadata)

    run_reference = run.to_reference()
    sample_list: List(Sample) = []

    for sample_name in sample_dict:
        metadata.loc[metadata["sample_name"] == sample_name, "haveMetaData"] = True
        metadata.loc[metadata["sample_name"] == sample_name, "haveReads"] = True

        sample = Sample(name=run.sample_name_generator(sample_name))
        sample["run"] = run_reference
        sample["display_name"] = sample_name
        sample_exists = False

        for i in range(len(samples)):
            if samples[i]["name"] == sample_name:
                print(f"Sample {sample_name} exists")
                sample_exists = True
                sample = samples[i]
        
        if run_mode == "SEQ":
            #samples collection 
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

            sample_metadata = metadata.loc[metadata['sample_name'] == sample_name].to_dict(orient = 'records')[0] # more stable to missing fields
            sample_metadata['filenames'] = list(sample_metadata['filenames']) # changing from tuple to list to match original

            sample_info = Category(value={
                "name": "sample_info",
                "component": {"id": component["_id"], "name": component["name"]},
                "summary": sample_metadata
            })
            sample.set_category(sample_info)
            print(f"accurately set the categories for the sample {sample_name} with run mode {run_mode}")
        elif run_mode == "ASM":
            #insert basic information into database using bifrostlib to mimic information obtained for NGS sequence data when running additional components
            fasta_file_path = os.path.abspath(os.path.join(input_folder, sample_dict[sample_name][0]))
            fasta_filename = os.path.basename(fasta_file_path)
            fasta_fileprefix = os.path.splitext(fasta_filename)[0]
            total_len, num_contigs, n50, mean_gc = save_contigs_data(fasta_file_path)

            #equivalent to the collection called "paired_reads" under "samples" category
            assembly = Category(value={
                "name": "assembly",
                "component": {"id": component["_id"], "name": component["name"]},
                "summary": {
                    "data": [
                        os.path.abspath(os.path.join(input_folder, sample_dict[sample_name][0]))
                    ],
                },
            })
            sample.set_category(assembly)

            # some of these info should perhaps be changed in the future to accomodate the information extracted for the sequencing reads
            creation_timestamp = os.path.getctime(fasta_file_path)
            creation_date = datetime.fromtimestamp(creation_timestamp).strftime("%Y-%m-%d")
            timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

            sample_info = Category(value={
                "name": "sample_info",
                "component": {"id": component["_id"], "name": component["name"]},
                "summary": {
                    "sample_name":fasta_fileprefix,
                    "provided_species":metadata["provided_species"].iloc[0],
                    "institution":metadata["institution"].iloc[0],
                    "group":metadata["group"].iloc[0],
                    "experiment_name":metadata["experiment_name"].iloc[0],
                    "sequence_run_date":metadata["sequence_run_date"].iloc[0],
                    "sofi_sequence_id":metadata["sofi_sequence_id"].iloc[0],
                    "filenames":[metadata["filenames"].iloc[0]],
                    "haveReads":False,
                    "haveMetaData":True,
                    "haveAsm":True
                },
                "metadata": {
                    "created_at": creation_date,
                    "updated_at": timestamp
                },
                "version": {
                    "schema": ["v0_0_0"]
                }
            })
            sample.set_category(sample_info)

            species_detection = Category(value={
                "name": "species_detection",
                "component": {"id": component["_id"], "name": "provided_metadata_species"},
                "summary": {
                    "percent_unclassified":0.0,
                    "percent_classified_species_1":1.0,
                    "name_classified_species_1":metadata["provided_species"].iloc[0],
                    "percent_classified_species_2":0.0,
                    "name_classified_species_2":metadata["provided_species"].iloc[0],
                    "detected_species":metadata["provided_species"].iloc[0],
                    "species":metadata["provided_species"].iloc[0],
                },
                "metadata": {
                    "created_at": creation_date,
                    "updated_at": timestamp
                },
                "version": {
                    "schema": ["v0_0_0"]
                }
            })
            sample.set_category(species_detection)
            
            # contigs category with the stats we just computed
            contigs = Category(value={
                "name": "contigs",
                "component": {"id": component["_id"], "name": "assembly"},
                "summary": {
                    "data": fasta_file_path,
                    "num_contigs": num_contigs,
                    "total_length": total_len,
                    "n50": n50,
                    "gc_mean": mean_gc,
                },
            })
            sample.set_category(contigs)
        try:
            sample.save()
        except DuplicateKeyError:
            print(f"Sample {sample_name} exists - reusing")
        sample_list.append(sample)

    run['component_subset'] = component_subset # this might just be for annotating in the db
    #run["type"] = run_type
    run["path"] = os.getcwd()

    if run_mode == "SEQ":
        run["type"] = run_type
        run["issues"] = {
            "duplicated_samples": list(metadata[metadata['duplicated_sample_names'] == True]['sample_name']),
            "changed_sample_names": list(metadata[metadata['changed_sample_names'] == True]['sample_name']),
            "unused_files": unused_files,
            "samples_without_reads": list(metadata[metadata['haveReads'] == False]['sample_name']),
            "samples_without_metadata": list(metadata[metadata['haveMetaData'] == False]['sample_name']),
        }
    elif run_mode == "ASM":
        run["type"] = "assembly"
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

        run, samples, run_mode = initialize_run(run=run,
                                                samples=samples,
                                                component=args.component,
                                                input_folder=args.reads_folder,
                                                run_metadata=args.run_metadata,
                                                run_type=args.run_type,
                                                rename_column_file=args.run_metadata_column_remap,
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

    print(f"Done with output directory: {args.outdir}")
    print("Done, to run execute bash run_script.sh")

# if __name__ == "__main__":
#     parse_args(sys.argv[1:])
