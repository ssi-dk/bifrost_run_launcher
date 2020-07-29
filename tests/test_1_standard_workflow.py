import os
import pymongo
import pytest
import argparse
from bifrost__run_launcher import launcher

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
    parser = launcher.parser()
    args: argparse.Namespace = parser.parse_args(["--install"])
    launcher.run_program(args)

def test_pipeline(mydb, tmp_path):
    test_install_component(mydb)
    d = tmp_path / "samples"
    d.mkdir()
    p = d / "Sample1_R1.fastq.gz"
    p.write_text("text")
    p = d / "Sample1_R2.fastq.gz"
    p.write_text("text")
    parser = launcher.parser()
    args: argparse.Namespace = parser.parse_args([
        "-pre", "examples/pre_script.sh",
        "-per", "examples/per_sample_script.sh",
        "-post", "examples/post_script.sh",
        "-meta", "examples/run_metadata.tsv",
        "-reads", str(d),
        "-name", "test_run",
        "-type", "test"
    ])
    launcher.run_program(args)
    assert os.path.isfile("run.yaml")
    assert os.path.isfile("samples.yaml")
    assert os.path.isfile("run_script.sh")