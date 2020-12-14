from argparse import Namespace
import pytest
from bifrostlib import common
from bifrostlib import datahandling
from bifrostlib import database_interface
from bifrostlib.datahandling import ComponentReference
from bifrostlib.datahandling import Component
from bifrostlib.datahandling import SampleReference
from bifrostlib.datahandling import Sample
from bifrostlib.datahandling import RunReference
from bifrostlib.datahandling import Run
from bifrost_run_launcher import launcher
import pymongo
import os
import shutil



@pytest.fixture
def test_connection():
    assert datahandling.has_a_database_connection()
    assert "TEST" in os.environ['BIFROST_DB_KEY'].upper()  # A very basic piece of protection ensuring the word test is in the DB

class TestBifrostRunLauncher:
    json_entries = [{"_id": {"$oid": "000000000000000000000001"}, "name": "test_component1"}]
    bson_entries = [database_interface.json_to_bson(i) for i in json_entries]

    @pytest.fixture
    def setUp(self, test_connection):
        client = pymongo.MongoClient(os.environ['BIFROST_DB_KEY'])
        db = client.get_database()
        db.drop_collection("components")
        launcher.initialize()

    def test_info(self, setUp):
        launcher.run_pipeline(["--info"])

    def test_help(self, setUp):
        launcher.run_pipeline(["--help"])

    def test_pipeline(self, setUp):
        bifrost_config_and_data_path = "/bifrost/test_data"
        if os.path.isdir(f"{bifrost_config_and_data_path}/test_dir"):
            shutil.rmtree(f"{bifrost_config_and_data_path}/test_dir")

        os.mkdir(f"{bifrost_config_and_data_path}/test_dir")
        test_args = Namespace(
            outdir=f"{bifrost_config_and_data_path}/test_dir",
            pre_script=f"{bifrost_config_and_data_path}/pre.sh",
            per_sample_script=f"{bifrost_config_and_data_path}/per_sample.sh",
            post_script=f"{bifrost_config_and_data_path}/post.sh",
            run_metadata=f"{bifrost_config_and_data_path}/run_metadata.tsv",
            reads_folder=f"{bifrost_config_and_data_path}/read_data",
            run_name="bifrost_test",
            run_type="test",
            run_id=None,
            run_metadata_column_remap=None
            )
        launcher.run_pipeline(test_args)
        assert os.path.isfile(f"{bifrost_config_and_data_path}/test_dir/run_script.sh")
        assert os.path.isfile(f"{bifrost_config_and_data_path}/test_dir/run.yaml")
        assert os.path.isfile(f"{bifrost_config_and_data_path}/test_dir/samples.yaml")
        shutil.rmtree(f"{bifrost_config_and_data_path}/test_dir")
        assert not os.path.isdir(f"{bifrost_config_and_data_path}/test_dir")


