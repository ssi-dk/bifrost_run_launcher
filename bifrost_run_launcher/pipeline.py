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
from bifrostlib import common
from bifrostlib.datahandling import RunReference
from bifrostlib.datahandling import Run
from bifrostlib.datahandling import Sample
from bifrostlib.datahandling import SampleReference
from bifrostlib.datahandling import Category
from bifrostlib.datahandling import Component
from bifrostlib.datahandling import ComponentReference
from bifrostlib.datahandling import SampleComponent
from bifrostlib.datahandling import SampleComponentReference
import pprint
import pymongo
from typing import List, Set, Dict, TextIO, Pattern, Tuple,Optional
from pymongo.errors import DuplicateKeyError
from Bio import SeqIO
from datetime import datetime
import gzip

os.umask(0o002)

def parse_directory(directory: str, 
                    run_mode: str, 
                    file_name_list: List[Tuple[str,str]], 
                    run_metadata: pd.DataFrame) -> Tuple[Dict, List[str]]:
    
    all_files: Set[str] = set(os.listdir(directory))
    unused_files: Set[str] = set(all_files)
    sample_dict = {}
    
    #define extensions for what is assumed to be unique to sequence reads and assemblies to differentiate in metadata
    sequence_ext = [".fq", ".fastq"]
    if run_mode == "ASM":
        sequence_ext = [".fa", ".fasta", ".fas", ".fna"]

    for sample_files in file_name_list:
        # Downstream it is assumed that there are exactly two sequence files, 
        # so we test and complain here if that is not the case.

        base, ext = os.path.splitext(sample_files[0])  # Extract first extension
        
        if ext == ".gz":  # Handle compressed files
            base, ext = os.path.splitext(base)  # Extract real file type before .gz

        if ext.lower() in sequence_ext:
            # For paired-end sequence read files - ensure exactly two files exist
            if run_mode == "SEQ":
                if len(sample_files) != 2:
                    print("Sample files:\n"+"\n".join(sample_files),file=sys.stderr)
                    raise ValueError(f"Error: Sample {sample_files} has {len(sample_files)} sequence files, it must have exactly two read files")
            else:
                # ASM
                if len(sample_files) != 1:
                    raise ValueError(f"Error: Sample {sample_files} has {len(sample_files)} assembly files, it must have exactly one assembly file.")
        else:
            raise ValueError(f"Error: Sample {sample_files[0]} extension {ext} is not compatible with bifrost run mode {run_mode} {sequence_ext}")

        if all_files.issuperset(sample_files):
            unused_files.difference_update(sample_files)
            sample_name = run_metadata.loc[lambda df: df["filenames"] == sample_files, "sample_name"]
            for n in sample_name:
                sample_dict[n] = list(sample_files)
        else:
            print(f"[WARNING] Sample files {sample_files} not in {directory}",file=sys.stderr)

    unused_seq_files = [ x for x in unused_files if not os.path.splitext(x)[1] in ['.tsv', '.xlsx'] ]
    return (sample_dict, unused_seq_files)

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
        
        if len(missing_files) > 0:
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

def get_sample_names(metadata: pd.DataFrame) -> List[str]:
    return list(set(metadata["sample_name"].tolist()))

def get_file_pairs(metadata: pd.DataFrame) -> List[Tuple[str,str]]:
    return list(set(metadata["filenames"].tolist()))

def initialize_run(run: Run, 
                   component: Component, 
                   input_folder: str = ".",
                   run_metadata: str = "run_metadata.txt", 
                   run_type: str = None, 
                   run_mode: str = "SEQ",
                   rename_column_file: str = None,
                   component_subset: str = "ccc,aaa,bbb"
                   ) -> Tuple[Run, List[SampleReference]]:
    
    metadata = format_metadata(run_metadata, rename_column_file)
    file_names_in_metadata = get_file_pairs(metadata)
    sample_dict, unused_files = parse_directory(input_folder, run_mode, file_names_in_metadata, metadata)

    run_reference = run.to_reference()
    sample_list: List[SampleReference] = []

    for sample_name in sample_dict:
        metadata.loc[metadata["sample_name"] == sample_name, "haveMetaData"] = True

        # existing sample lookup
        sequence_id = run.sample_name_generator(sample_name)
        sample = Sample.load(SampleReference(name = sequence_id))
        if sample is None:
            sample = Sample(name = sequence_id)
            sample["run"] = run_reference.json
            sample["display_name"] = sample_name
        else:
            # all components are re-run even for existing samples
            sample = initialize_sample_properties(sample, None)
        
        # sample db record
        if run_mode == "SEQ":
            metadata.loc[metadata["sample_name"] == sample_name, "haveReads"] = True
            
            # paired reads needed
            read1, read2 = sample_dict[sample_name][0], sample_dict[sample_name][1]
            read1_path = os.path.abspath(os.path.join(input_folder, read1))
            read2_path = os.path.abspath(os.path.join(input_folder, read2))
            
            #samples collection 
            paired_reads = Category(value={
                "name": "paired_reads",
                "component": {"id": component["_id"], 
                              "name": component["name"]}, # giving paired reads component id?
                "summary": {
                        "data": [
                            read1_path,
                            read2_path
                        ]
                }
            })
            sample.set_category(paired_reads)
            print(f"accurately set the categories for the sample {sample_name} with run mode {run_mode}")
        elif run_mode == "ASM":
            metadata.loc[metadata["sample_name"] == sample_name, "haveAsm"] = True

            #equivalent to the collection called "paired_reads" under "samples" category
            event_fasta = sample_dict[sample_name][0]
            fasta_file_path = os.path.abspath(os.path.join(input_folder,event_fasta))

            events = Category(value={
                "name": "events",
                "component": {"id": component["_id"], 
                              "name": component["name"]},
                "summary": {
                    "data": fasta_file_path
                },
            })
            sample.set_category(events)

            # some of these info should perhaps be changed in the future to accomodate the information extracted for the sequencing reads
            creation_timestamp = os.path.getctime(fasta_file_path)
            creation_date = datetime.fromtimestamp(creation_timestamp).strftime("%Y-%m-%d")
            timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

            row = metadata.loc[metadata["sample_name"] == sample_name].iloc[0]
            species = row["provided_species"]

            species_detection = Category(value={
                "name": "species_detection",
                "component": {"id": component["_id"], 
                              "name": "provided_metadata_species"},
                "summary": {
                    "species": species,
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
        else:
            pass
        
        # sample_info is common to both modes
        sample_metadata = metadata.loc[metadata['sample_name'] == sample_name].to_dict(orient = 'records')[0] # more stable to missing fields
        sample_metadata['filenames'] = list(sample_metadata['filenames']) # changing from tuple to list to match original

        sample_info = Category(value={
            "name": "sample_info",
            "component": {"id": component["_id"], 
                            "name": component["name"]},
            "summary": sample_metadata
        })
        sample.set_category(sample_info)

        try:
            sample.save()
        except DuplicateKeyError:
            print(f"Sample {sample_name} exists - reusing")
        sample_list.append(sample.to_reference())

    # for Run record
    if component_subset is None:
        # all components from env var
        if run_mode == "SEQ":
            component_subset = os.environ['BIFROST_COMPONENTS'].replace(" ", ",")
        else:
            component_subset = os.environ['BIFROST_COMPONENTS_ASM'].replace(" ", ",")
    run['component_subset'] = component_subset
    run["path"] = os.getcwd()
    run["type"] = run_type
    run.samples = sample_list

    # issues
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
            "samples_without_contigs": list(metadata[metadata['haveAsm'] == False]['sample_name']),
            "samples_without_metadata": list(metadata[metadata['haveMetaData'] == False]['sample_name']),
        }
    else:
        pass

    # insert run record
    run.save()

    with open("run.yaml", "w") as fh:
        fh.write(pprint.pformat(run.json))
    with open("samples.yaml", "w") as fh:
        for sample in sample_list:
            fh.write(pprint.pformat(sample.json))

    return (run, sample_list)

def initialize_sample_properties(sample: Sample, component_names: List[str] | None) -> Sample:
    # reset Sample record
    if component_names is None:
        sample["components"] = []
        sample["categories"] = {}
    else:
        # remove those re-run
        # ?WHY Should components with different versions be also removed?
        components_to_keep: List[Dict] = []
        for comp in sample["components"]:
            if comp['name'].replace('__5e385d4', '') not in component_names:
                components_to_keep.append(comp)
        sample["components"] = components_to_keep
        categories_to_keep: List[Category] = []
        for cat_name in sample["categories"]:
            category: Category = sample.get_category(cat_name)
            if category['component']:
                if category['component']['name'].replace('__5e385d4', '') not in component_names:
                    categories_to_keep.append(category)
            else:
                #mainly serotypers
                categories_to_keep.append(category)
        sample["categories"] = {}
        for kept_cat in categories_to_keep:
            sample.set_category(kept_cat)
    return sample

def initialize_component_statuses(run: Run, samples: List[SampleReference], component_names: List[str]) -> None:
    for component_name in component_names:
        if component_name.startswith("cge_mlst"):
            component_name = component_name + "__5e385d4"
        component_ref = ComponentReference(name=component_name)
        component: Component = Component.load(reference=component_ref)
        if component is None:
            raise Exception(f"invalid component passed {component_ref}")
        for sample_ref in samples:
            sample: Sample = Sample.load(sample_ref)
            if sample is None:
                raise Exception(f"invalid sample passed {sample_ref}")
            samplecomponent_ref = SampleComponentReference(
                name=SampleComponentReference.name_generator(sample.to_reference(), component.to_reference())
            )
            samplecomponent = SampleComponent.load(samplecomponent_ref)
            if samplecomponent is None:
                samplecomponent = SampleComponent(
                    sample_reference=sample.to_reference(),
                    component_reference=component.to_reference()
                )
            # reset result and set status to queued
            samplecomponent["results"] = {}
            samplecomponent["categories"] = {}
            common.set_status_and_save(sample, samplecomponent, "Queued")
    return

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

def replace_components_list_in_script(script: str, component_subset: str) -> str:
    component_subset_str = component_subset.replace(",", " ")
    positions_to_replace = re.findall(re.compile(r"\$BIFROST_COMPONENTS_?[AMS]{0,3}"), script)
    for item in positions_to_replace:
        script = script.replace(item, component_subset_str)
    return script

def generate_run_script(run: Run, samples: List[SampleReference], pre_script_location: str, per_sample_script_location: str, post_script_location: str, component_subset: str) -> str:
    script = ""
    if pre_script_location is not None:
        with open(pre_script_location, "r") as pre_script_file:
            pre_script = pre_script_file.read()
            script = script + replace_run_info_in_script(pre_script, run)

    if per_sample_script_location is not None:
        with open(per_sample_script_location, "r") as per_sample_script_file:
            per_sample_script = per_sample_script_file.read()
        per_sample_script = replace_run_info_in_script(per_sample_script, run)
        if component_subset is not None:
            per_sample_script = replace_components_list_in_script(per_sample_script, component_subset)
        for sample in samples:
            script = script + replace_sample_info_in_script(per_sample_script, sample)

    if post_script_location is not None:
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
        if run is None and args.run_id is not None:
            # mistyped id
            raise ValueError(f"_id={args.run_id} not in db.")
        elif run is None:
            # new Run
            run: Run = Run(name=args.run_name)
            run.save()
    else:
        run: Run = Run(name=args.run_name)
        run.save()

    component_names = None
    if "_id" not in run.json or args.sample_subset is None:
        # new or fully re-run Run
        if args.debug:
            print(f"{run = }\n")
        
        if args.sample_subset is not None:
            print(f"[WARNING] {",".join(missentered_subset_samples)} not present in run.")

        run, samples = initialize_run(run=run,
                                    component=args.component,
                                    input_folder=args.reads_folder,
                                    run_metadata=args.run_metadata,
                                    run_type=args.run_type,
                                    run_mode=args.run_mode,
                                    rename_column_file=args.run_metadata_column_remap,
                                    component_subset=args.component_subset)
        
        print(f"Run {run['name']} and samples newly added to DB")
    elif args.sample_subset is not None:
        # re-run specific samples from run
        print(f"Re-processing samples from run {run['name']}") # we only want to subset samples from a pre-existing run
        if args.sample_subset is not None:
            sample_subset = args.sample_subset.split(",")
            missentered_subset_samples = []
            samples: List[SampleReference] = []
            if len(run.samples) >= 1:
                ran_samples = [x['name'] for x in run.samples]
                for entered_sample in sample_subset:
                    entered_sample_id = run.sample_name_generator(entered_sample)
                    if entered_sample_id not in ran_samples:
                        missentered_subset_samples.append(entered_sample)
                    else:
                        samples.append(SampleReference(name = entered_sample_id))
            else:
                raise ValueError(f"Wrong input: sample_subset can not be used with new Run, modify metadata sheet instead")
            if len(missentered_subset_samples) > 0:
                print(f"[WARNING] {",".join(missentered_subset_samples)} not present in run.")
        
        if args.re_run_components:
            # re-run specific components only for these samples
            if args.component_subset is None:
                raise ValueError(f"Wrong input: component_subset can not be empty if re_run_components flag used")
            component_names = [re.sub(r"_v(\d)", r"__v\1", x) for x in args.component_subset.replace("bifrost_", "").split(",")]

        for sample_ref in samples:
            sample = Sample.load(sample_ref)
            sample = initialize_sample_properties(sample, component_names)
            sample.save()
    else:
        pass

    if args.debug:
        print("run")
        print(run)
        print("samples")
        print(samples)

    # make a list for all the components to run
    if component_names is None:
        if args.component_subset is None:
            if args.run_mode == "SEQ":
                component_list = os.environ['BIFROST_COMPONENTS'].replace(" ", ",")
            else:
                component_list = os.environ['BIFROST_COMPONENTS_ASM'].replace(" ", ",")
        else:
            component_list = args.component_subset
        component_names = [re.sub(r"_v(\d)", r"__v\1", x) for x in component_list.replace("bifrost_", "").split(",")]

    # clean up and initialize statuses for samples, sample_components that are being run
    initialize_component_statuses(run, samples, component_names)

    if not args.re_run_components:
        # per shell scripts are different for SEQ and ASM
        script = generate_run_script(
            run,
            samples,
            args.pre_script,
            args.per_sample_script,
            args.post_script,
            args.component_subset)
            
        with open("run_script.sh", "w") as fh:
            fh.write(script)

        print(f"Done with output directory: {args.outdir}")
        print("Done, to run execute bash run_script.sh")
    else:
        print(f"Done with samples {args.sample_subset} and \ncomponents {args.component_subset}")
