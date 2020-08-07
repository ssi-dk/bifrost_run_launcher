import os
import pymongo
import pytest
import argparse
import yaml
import subprocess
from bifrost_run_launcher import launcher as brl
# Test data from bifrost_test_data git repo

@pytest.fixture
def mydb():
    if os.getenv("BIFROST_DB_KEY", None) is not None:
        db_connection = pymongo.MongoClient(os.getenv("BIFROST_DB_KEY"))
        return db_connection.get_database()
    else:
        raise ValueError("BIFROST_DB_KEY not set")

def test_db_connection(mydb):
    mydb.list_collection_names()

def test_clear_db(mydb):
    os.chdir('/bifrost_test_data/')
    col_components = mydb["components"]
    col_samples = mydb["samples"]
    col_runs = mydb["runs"]
    col_components.drop()
    col_samples.drop()
    col_runs.drop()


def test_install_component(mydb):
    test_clear_db(mydb)
    args: argparse.Namespace = brl.parser(["--install"])
    brl.run_program(args)

def test_pipeline_no_data(mydb, tmp_path):
    test_install_component(mydb)
    d = tmp_path / "samples"
    d.mkdir()
    p = d / "S1_R1.fastq.gz"
    p.write_text("text")
    p = d / "S1_R2.fastq.gz"
    p.write_text("text")
    # Resources folder is made with Dockerfile in dev mode
    args = brl.parser([
        "-pre", "/bifrost_test_data/pre.sh",
        "-per", "/bifrost_test_data/per_sample.sh",
        "-post", "/bifrost_test_data/post.sh",
        "-meta", "/bifrost_test_data/run_metadata.tsv",
        "-reads", str(d),
        "-name", "test_run",
        "-type", "test"
    ])
    brl.run_program(args)
    assert os.path.isfile("run.yaml")
    assert os.path.isfile("samples.yaml")
    assert os.path.isfile("run_script.sh")

def test_pipeline_with_data(mydb, tmp_path):
    test_install_component(mydb)
    if not (os.path.isfile("/bifrost_test_data/read_data/S1_R1.fastq.gz") and os.path.isfile("/bifrost_test_data/read_data/S1_R2.fastq.gz")):
        process = subprocess.Popen(
                "bash download_S1.sh",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                cwd="/bifrost_test_data/read_data/")
        process_out, process_err = process.communicate()
    args = brl.parser([
        "-pre", "/bifrost_test_data/pre.sh",
        "-per", "/bifrost_test_data/per_sample.sh",
        "-post", "/bifrost_test_data/post.sh",
        "-meta", "/bifrost_test_data/run_metadata.tsv",
        "-reads", "/bifrost_test_data/read_data",
        "-name", "test_run",
        "-type", "test"
    ])
    brl.run_program(args)
    assert os.path.isfile("run.yaml")
    with open("run.yaml", "r") as file_handle:
        run_doc = yaml.safe_load(file_handle)
    print(run_doc["samples"])
    assert(run_doc["samples"][0]["name"] == "S1")
    assert os.path.isfile("samples.yaml")
    assert os.path.isfile("run_script.sh")