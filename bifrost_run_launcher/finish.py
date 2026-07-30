#!/usr/bin/env python3
"""
Finishing program for paired end Illumina reads
"""
import re
import os
import sys
from bifrostlib import common
from bifrostlib.datahandling import RunReference
from bifrostlib.datahandling import Run
from bifrostlib.datahandling import Sample
from bifrostlib.datahandling import SampleReference
from bifrostlib.datahandling import Component
from bifrostlib.datahandling import ComponentReference
from bifrostlib.datahandling import SampleComponent
from bifrostlib.datahandling import SampleComponentReference
from typing import List, Set, Dict, TextIO, Pattern, Tuple,Optional

os.umask(0o002)

def finalize_component_statuses(run: Run, samples: List[SampleReference], component_names: List[str]) -> None:
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
                print(f"[WARNING] Invalid sample_component passed {samplecomponent_ref}", file=sys.stderr)
                continue
            print(f"{samplecomponent['name']}: {samplecomponent['status']}")
            if samplecomponent['status'] in ["Queued", "Running"]:
                common.set_status_and_save(sample, samplecomponent, "Failure")
    return

def finish_pipeline(args) -> None:
    # load Run
    run: Run = Run.load(RunReference(_id = args.run_id, name = args.run_name))
    if run is None:
        raise ValueError(f"Error: Run not found for {args.run_name}")
    if args.run_mode is None:
        # aliases
        if run.type is None or run.type in ['run']:
            args.run_mode = 'SEQ'
        else:
            args.run_mode = 'ASM'
    # find processed Samples
    sample_references: List[SampleReference] = []
    if args.sample_subset is None:
        sample_references = run.samples
    else:
        sample_subset = args.sample_subset.split(",")
        sample_long_subset = [run.sample_name_generator(entered_sample) for entered_sample in sample_subset]
        for sample_ref in run.samples:
            if sample_ref['name'] in sample_long_subset:
                sample_references.append(sample_ref)
    # find components
    component_list: str = ""
    if args.component_subset is None:
        if args.run_mode == "SEQ":
            component_list = os.environ['BIFROST_COMPONENTS'].replace(" ", ",")
        else:
            component_list = os.environ['BIFROST_COMPONENTS_ASM'].replace(" ", ",")
    else:
        component_list = args.component_subset
    component_names = [re.sub(r"_v(\d)", r"__v\1", x) for x in component_list.replace("bifrost_", "").split(",")]

    # if status is Queued/Running, set it to Failure
    finalize_component_statuses(run, sample_references, component_names)
    return
