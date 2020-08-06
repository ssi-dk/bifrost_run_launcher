import os
import pymongo
import pytest
import argparse
import yaml
from bifrost_run_launcher import launcher as brl

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
    p = d / "Sample1_R1.fastq.gz"
    p.write_text("text")
    p = d / "Sample1_R2.fastq.gz"
    p.write_text("text")
    # Resources folder is made with Dockerfile in dev mode
    args = brl.parser([
        "-pre", "/bifrost_run_launcher/examples/pre_script.sh",
        "-per", "/bifrost_run_launcher/examples/per_sample_script.sh",
        "-post", "/bifrost_run_launcher/examples/post_script.sh",
        "-meta", "/bifrost_run_launcher/examples/run_metadata.tsv",
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
    # Resources folder is made with Dockerfile in dev mode
    args = brl.parser([
        "-pre", "/bifrost_run_launcher/examples/pre_script.sh",
        "-per", "/bifrost_run_launcher/examples/per_sample_script.sh",
        "-post", "/bifrost_run_launcher/examples/post_script.sh",
        "-meta", "/bifrost_run_launcher/examples/run_metadata.tsv",
        "-reads", "/bifrost_run_launcher/examples",
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