#!/usr/bin/env python3
"""
Initialization program for paired end Illumina reads
"""
import re
import os
from sys import stderr
import traceback
import pandas
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
from pymongo import errors.DuplicateKeyError as DuplicateKeyError


os.umask(0o002)


def parse_directory(directory: str, file_name_list: List[Tuple[str,str]], run_metadata: pandas.DataFrame, run_metadata_filename: str) -> Tuple[Dict, List[str]]:
    all_files: Set[str] = set(os.listdir(directory))
    unused_files: Set[str] = all_files
    sample_dict = {}
    for sample_files in file_name_list:
        # Downstream it is assumed that there are exactly two sequence files, 
        # so we test and complain here if that is not the case.
        if len(sample_files) != 2:
            print("Sample files:\n"+"\n".join(sample_files),file=sys.stderr)
            raise ValueError("Number of sequence files is not two")
        if all_files.issuperset(sample_files):
            unused_files.difference_update(sample_files)
            sample_name = run_metadata.loc[lambda df: df["filenames"] == sample_files, "sample_name"]
            for n in sample_name:
                sample_dict[n] = list(sample_files)
    unused_files.discard(run_metadata_filename)
    return (sample_dict, list(unused_files))


def format_metadata(run_metadata: TextIO, rename_column_file: TextIO = None) -> pandas.DataFrame:
    df = None
    try:
        df = pandas.read_table(run_metadata)
        if rename_column_file is not None:
            with open(rename_column_file, "r") as rename_file:
                df = df.rename(columns=json.load(rename_file))
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        samples_no_index = df[df["sample_name"].isna()].index # drop unnamed samples
        samples_no_files_index = df[df["filenames"].isnull()].index # drop samples missing reads
        idx_to_drop = samples_no_index.union(samples_no_files_index)
        missing_files = ", ".join([df["sample_name"].iloc[i] for i in samples_no_files_index])
        print(f"samples {missing_files} missing files.")
        df = df.drop(idx_to_drop)
        #df = df.drop(samples_no_index)
        df["sample_name"] = df["sample_name"].astype('str')
        df["temp_sample_name"] = df["sample_name"]
        df["sample_name"] = df["sample_name"].apply(lambda x: x.strip())
        df["sample_name"] = df["sample_name"].str.replace(re.compile("[^a-zA-Z0-9-_]"), "_", regex=True)
        df["changed_sample_names"] = df['sample_name'] != df['temp_sample_name']
        df["duplicated_sample_names"] = df.duplicated(subset="sample_name", keep="first")
        df["haveReads"] = False
        df["haveMetaData"] = True
        df["filenames"] = df["filenames"].apply(lambda x: tuple(x.strip().split('/')))
        df = df.map(lambda x: None if pandas.isna(x) else x)
        return df
    except:
        with pandas.option_context('display.max_rows', None, 'display.max_columns', None):
            print(df, file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            raise Exception("bad metadata and/or rename column file")

def get_sample_names(metadata: pandas.DataFrame) -> List["str"]:
    return list(set(metadata["sample_name"].tolist()))

def get_file_pairs(metadata: pandas.DataFrame) -> List[Tuple[str,str]]:
    return list(set(metadata["filenames"].tolist()))


def initialize_run(run: Run, samples: List[Sample], component: Component, input_folder: str = ".",
                   run_metadata: str = "run_metadata.txt", run_type: str = None, rename_column_file: str = None,
                   #regex_pattern: str = r"^(?P<sample_name>[a-zA-Z0-9_\-]+?)(_S[0-9]+)?(_L[0-9]+)?_(R?)(?P<paired_read_number>[1|2])(_[0-9]+)?(\.fastq\.gz)$",
                   component_subset: str = "ccc,aaa,bbb"
                   ) -> Tuple[Run, List[Sample]]:
    metadata = format_metadata(run_metadata, rename_column_file)
    file_names_in_metadata = get_file_pairs(metadata)
    sample_dict, unused_files = parse_directory(input_folder, file_names_in_metadata, metadata, run_metadata)
    run_reference = run.to_reference()
    for sample_name in sample_dict:
        #print(sample_name)
        metadata.loc[metadata["sample_name"] == sample_name, "haveMetaData"] = True
        metadata.loc[metadata["sample_name"] == sample_name, "haveReads"] = True
        sample = Sample(name=run.sample_name_generator(sample_name))
        sample["run"] = run_reference
        sample["display_name"] = sample_name
        sample_exists = False
        for i in range(len(samples)):
            if samples[i]["name"] == sample_name:
                sample_exists = True
                sample = samples[i]
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
        if sample_exists is False:
            samples.append(sample)
    run['component_subset'] = component_subset # this might just be for annotating in the db
    run["type"] = run_type
    run["path"] = os.getcwd()
    run["issues"] = {
        "duplicated_samples": list(metadata[metadata['duplicated_sample_names'] == True]['sample_name']),
        "changed_sample_names": list(metadata[metadata['changed_sample_names'] == True]['sample_name']),
        "unused_files": unused_files,
        "samples_without_reads": list(metadata[metadata['haveReads'] == False]['sample_name']),
        "samples_without_metadata": list(metadata[metadata['haveMetaData'] == False]['sample_name']),
    }
    run.samples = [i.to_reference() for i in samples]
    run.save()

    with open("run.yaml", "w") as fh:
        fh.write(pprint.pformat(run.json))
    with open("samples.yaml", "w") as fh:
        for sample in samples:
            fh.write(pprint.pformat(sample.json))

    return (run, samples)


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
        run, samples = initialize_run(run=run, samples=samples, component=args.component, input_folder=args.reads_folder, run_metadata=args.run_metadata, run_type=args.run_type, rename_column_file=args.run_metadata_column_remap, component_subset=args.component_subset)
        
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

# if __name__ == "__main__":
#     parse_args(sys.argv[1:])
