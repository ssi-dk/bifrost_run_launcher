#!/usr/bin/env python3
"""
Launcher file for accessing dockerfile commands
"""
import argparse
import os
import sys
import traceback
from bifrost_run_launcher import pipeline, finish
from bifrostlib import datahandling
from bifrostlib.datahandling import Component
from bifrostlib.datahandling import ComponentReference
import yaml
import pprint
from typing import List, Dict


global COMPONENT


def initialize():
    with open(os.path.join(os.path.dirname(__file__), 'config.yaml')) as fh:
        config: Dict = yaml.load(fh, Loader=yaml.FullLoader)

    if not(datahandling.has_a_database_connection()):
        raise ConnectionError("BIFROST_DB_KEY is not set or other connection error")

    global COMPONENT
    try:
        component_ref = ComponentReference(name=config["name"])
        COMPONENT = Component.load(component_ref)
        if COMPONENT is not None and '_id' in COMPONENT.json:
            return
        else:
            COMPONENT = Component(value=config)
            install_component()

    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
    return


def install_component():
    COMPONENT['install']['path'] = os.path.os.getcwd()
    print(f"Installing with path:{COMPONENT['install']['path']}")
    try:
        COMPONENT.save()
        print(f"Done installing")
    except:
        print(traceback.format_exc(), file=sys.stderr)
        sys.exit(0)


class types():
    def file(path):
        if os.path.isfile(path):
            return os.path.abspath(path)
        else:
            raise argparse.ArgumentTypeError(f"{path} #Bad file path")

    def directory(path):
        if os.path.isdir(path):
            return os.path.abspath(path)
        else:
            raise argparse.ArgumentTypeError(f"{path} #Bad directory path")


def parse_and_run(args: List[str]) -> None:
    description: str = (
        f"-Description------------------------------------\n"
        f"{COMPONENT['details']['description']}"
        f"------------------------------------------------\n"
        f"\n"
        f"-Environmental Variables/Defaults---------------\n"
        f"BIFROST_CONFIG_DIR: {os.environ.get('BIFROST_CONFIG_DIR','.')}\n"
        f"BIFROST_RUN_DIR: {os.environ.get('BIFROST_RUN_DIR','.')}\n"
        f"------------------------------------------------\n"
        f"\n"
    )

    # Using two parsers for UX so that install doesn't conflict while all the args still point to the main parser
    basic_parser = argparse.ArgumentParser(add_help=False) 
    basic_parser.add_argument(
        '--reinstall',
        action='store_true',
    )
    basic_parser.add_argument(
        '--info',
        action='store_true',
        help='Provides basic information on COMPONENT'
    )

    #Second parser for the arguements related to the program, everything can be set to defaults (or has defaults)
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Show arg values'
    )
    parser.add_argument(
        '-out', '--outdir',
        default=os.environ.get('BIFROST_RUN_DIR', os.getcwd()),
        help='Output directory'
    )
    parser.add_argument(
        '-pre', '--pre_script',
        help='Pre script template run before sample script',
        default=os.path.join(os.environ.get('BIFROST_INSTALL_DIR', os.getcwd()), "launcher_scripts","pre.sh"),
        type=types.file,
    )
    parser.add_argument(
        '-per', '--per_sample_script',
        help='Per sample script template run on each sample',
        default=os.path.join(os.environ.get('BIFROST_INSTALL_DIR', os.getcwd()), "launcher_scripts","per.sh"),
        type=types.file
    )
    parser.add_argument(
        '-post', '--post_script',
        help='Post script template run after sample script',
        default=os.path.join(os.environ.get('BIFROST_INSTALL_DIR', os.getcwd()), "launcher_scripts","post.sh"),
        type=types.file
    )
    parser.add_argument(
        '-meta', '--run_metadata',
        help='Run metadata tsv',
        type=types.file
    )
    parser.add_argument(
        '-reads', '--reads_folder',
        help='Run reads folder',
        type=types.directory
    )
    parser.add_argument(
        '-name', '--run_name',
        help='Run name, if not provided it will default to current folder name',
        default=None
    )
    parser.add_argument(
        '-type', '--run_type',
        default="run",
        help='Run type for metadata organization'
    )
    parser.add_argument(
        '-m', '--run_mode',
        default=None,
        help='Run mode for pipeline selection [SEQ, ASM]'
    )
    parser.add_argument(
        '-colmap', '--run_metadata_column_remap',
        help='Remaps metadata tsv columns to bifrost values',
        default=None if not os.path.isfile(os.path.join(os.environ.get('BIFROST_CONFIG_DIR', os.getcwd()), COMPONENT['options']['default_colmap'])) else os.path.join(os.environ.get('BIFROST_CONFIG_DIR', os.getcwd()), COMPONENT['options']['default_colmap']),
        type=types.file
    )
    parser.add_argument(
        '-id', '--run_id',
        default=None,
        help='For re-running a run'
    )
    parser.add_argument(
        '-recomp', '--re_run_components',
        action="store_true",
        help='For re-initializing a subset of sample components for sample(s)'
    )
    parser.add_argument(
        '-rerun', '--re_run',
        action="store_true",
        help='For re-running a run'
    )
    parser.add_argument( # get a way to replace the info in per script in pipeline.py
       '-co', '--component_subset',
       default=None,
       help='Component subset to run on samples. Use a comma for separation: bifrost_min_read_check_v2.2.10,bifrost_whats_my_species_v2.2.12,bifrost_assemblatron_v2.3.3'
    )
    parser.add_argument( # get a way to replace the info in per script in pipeline.py
       '-s', '--sample_subset',
       default=None,
       help='Sample subset to process, None will run all samples. Short names, use a comma for separation'
    )
    parser.add_argument(
        '-f', '--finish',
        action="store_true",
        help='Finalize statuses for sample components for sample(s) in run'
    )

    try:
        basic_options, extras = basic_parser.parse_known_args(args)
        if basic_options.reinstall:
            install_component()
            return None
        elif basic_options.info:
            show_info()
            return None
        else:
            pipeline_options, junk = parser.parse_known_args(extras)
            pipeline_options.component = COMPONENT # Want to access the component as well so forcing it as an option
            if pipeline_options.run_name is None:
                pipeline_options.run_name = os.path.abspath(pipeline_options.outdir).split("/")[-1]
            if pipeline_options.debug is True:
                print(pipeline_options)
            if pipeline_options.run_mode is None:
                # allow entry via Run.type instead of run_mode
                if pipeline_options.run_type in ['run']:
                    pipeline_options.run_mode = 'SEQ'
                else:
                    pipeline_options.run_mode = 'ASM'
            elif pipeline_options.run_mode == 'ASM':
                # in case of run_type not given with run_mode
                if pipeline_options.run_type in ['run']:
                    pipeline_options.run_type = 'events'
            else:
                pass
            if pipeline_options.finish is True:
                finish.finish_pipeline(pipeline_options)
            else:
                if pipeline_options.re_run_components:
                    if pipeline_options.sample_subset is None or pipeline_options.component_subset is None:
                        raise ValueError(f"Wrong input: component_subset and sample_subset can not be empty if re_run_components flag used")
                else:
                    if pipeline_options.run_metadata is None or pipeline_options.reads_folder is None:
                        raise ValueError(f"Wrong input: metadata and reads folder path is needed")

                run_pipeline(pipeline_options)
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)


def show_info():
    pprint.pprint(COMPONENT.json)

def run_pipeline(args: object):
    try:
        pipeline.run_pipeline(args)
    except:
        print(traceback.format_exc())


def main(args=sys.argv):
    initialize()
    parse_and_run(args)


if __name__ == '__main__':
    main()
