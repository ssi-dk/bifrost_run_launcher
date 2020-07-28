#!/usr/bin/env python3
"""
Launcher file for accessing dockerfile commands
"""
import argparse
import json
import subprocess
import os
import sys
import traceback
from bifrostlib import datahandling
from src import pipeline


COMPONENT: dict = datahandling.load_yaml(os.path.join(os.path.dirname(__file__), 'config.yaml'))


def parser():
    """
    Arg parsing via argparse
    """
    description: str = (
        f"-Description------------------------------------\n"
        f"{COMPONENT['details']['description']}"
        f"------------------------------------------------\n\n"
        f"*Run command************************************\n"
        f"docker run \ \n"
        f" -e BIFROST_DB_KEY=mongodb://<user>:<password>@<server>:<port>/<db_name> \ \n"
        f" {COMPONENT['install']['dockerfile']} \ \n"
        f"************************************************\n"
    )
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--install',
                        action='store_true',
                        help='Install component')
    parser.add_argument('-info', '--info',
                        action='store_true',
                        help='Provides basic information on component')
    parser.add_argument('-pre', '--pre_script',
                        help='Pre script template run before sample script')
    parser.add_argument('-per', '--per_sample_script',
                        help='Per sample script template run on each sample')
    parser.add_argument('-post', '--post_script',
                        help='Post script template run after sample script')
    parser.add_argument('-meta', '--run_metadata',
                        help='Run metadata tsv')
    parser.add_argument('-reads', '--reads_folder',
                        help='Run metadata tsv')
    parser.add_argument('-name', '--run_name',
                        default=None,
                        help='Run name, if not provided it will default to current folder name')
    parser.add_argument('-type', '--run_type',
                        default=None,
                        help='Run type for metadata organization')
    parser.add_argument('-metamap', '--run_metadata_column_remap',
                        default=None,
                        help='Remaps metadata tsv columns to bifrost values')
    #TODO: Put code in to utilize ID
    parser.add_argument('-id', '--run_id',
                        help='For re-running a run') 
    return parser


def run_program(args: argparse.Namespace):
    if not datahandling.check_db_connection_exists():
        message: str = (
            f"ERROR: Connection to DB not establised.\n"
            f"please ensure env variable BIFROST_DB_KEY is set and set properly\n"
        )
        print(message)
    else:
        print(datahandling.get_connection_info())

    if args.info:
        show_info()
    elif args.install:
        install_component()
    else:
        run_pipeline(args)


def show_info():
    """
    Shows information about the component
    """
    message: str = (
        f"Component: {COMPONENT['name']}\n"
        f"Version: {COMPONENT['version']}\n"
        f"Details: {json.dumps(COMPONENT['details'], indent=4)}\n"
        f"Requirements: {json.dumps(COMPONENT['requirements'], indent=4)}\n"
        f"Output files: {json.dumps(COMPONENT['db_values_changes']['files'], indent=4)}\n"
    )
    print(message)


def install_component():
    component: list[dict] = datahandling.get_components(component_names=[COMPONENT['name']])
    # if len(component) == 1:
    #     print(f"Component has already been installed")
    if len(component) > 1:
        print(f"Component exists multiple times in DB, please contact an admin to fix this in order to proceed")
    else:
        #HACK: Installs based on your current directory currently. Should be changed to the directory your docker/singularity file is
        #HACK: Removed install check so you can reinstall the component. Should do this in a nicer way
        COMPONENT['install']['path'] = os.path.os.getcwd()
        datahandling.post_component(COMPONENT)
        component: list[dict] = datahandling.get_components(component_names=[COMPONENT['name']])
        if len(component) != 1:
            print(f"Error with installation of {COMPONENT['name']} {len(component)}\n")
            exit()


def run_pipeline(args: object):
    """
    Runs pipeline
    """
    component: list[dict] = datahandling.get_components(component_names=[COMPONENT['name']])
    if len(component) == 0:
        print(f"component not found in DB, installing it:")
        datahandling.post_component(COMPONENT)
        component: list[dict] = datahandling.get_components(component_names=[COMPONENT['name']])
        if len(component) != 1:
            print(f"Error with installation of {COMPONENT['name']}\n")
            exit()

    else:
        try:
            optional_values: str = ""
            if args.run_name is not None:
                optional_values = f"{optional_values} -name {str(args.run_name)}"
            if args.run_type is not None:
                optional_values = f"{optional_values} -type {str(args.run_type)}"
            if args.run_type is not None:
                optional_values = f"{optional_values} -metamap {str(args.run_metadata_column_remap)}"
            if args.run_id is not None:
                optional_values = f"{optional_values} -id {str(args.run_id)}"
            pipeline.run_pipeline(args)
        except:
            print(traceback.format_exc())


if __name__ == '__main__':
    args: argparse.Namespace = parser().parse_args()
    run_program(args)