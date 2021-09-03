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
    component_name = "run_launcher__v2_2_6"
    test_dir = "/bifrost/test_data/output/test__run_launcher/"
    current_dir = os.getcwd()
    json_entries = [{"_id": {"$oid": "000000000000000000000001"}, "name": "test_component1"}]

    bson_entries = [database_interface.json_to_bson(i) for i in json_entries]

    @classmethod
    def setup_class(cls):
        client = pymongo.MongoClient(os.environ['BIFROST_DB_KEY'])
        db = client.get_database()
        cls.clear_all_collections(db)
        launcher.initialize()

    @classmethod
    def teardown_class(cls):
        client = pymongo.MongoClient(os.environ['BIFROST_DB_KEY'])
        db = client.get_database()
        cls.clear_all_collections(db)

    @staticmethod
    def clear_all_collections(db):
        db.drop_collection("components")
        db.drop_collection("hosts")
        db.drop_collection("run_components")
        db.drop_collection("runs")
        db.drop_collection("sample_components")
        db.drop_collection("samples")

    def test_info(self):
        launcher.run_pipeline(["--info"])

    def test_help(self):
        launcher.run_pipeline(["--help"])

    def test_pipeline(self):

        bifrost_config_and_data_path = "/bifrost/test_data"

        if os.path.isdir(self.test_dir):
            shutil.rmtree(self.test_dir)

        os.mkdir(self.test_dir)
        test_args = [
            "--outdir", f"{self.test_dir}/{self.component_name}",
            "--pre_script", f"{bifrost_config_and_data_path}/pre.sh",
            "--per_sample_script", f"{bifrost_config_and_data_path}/per_sample.sh",
            "--post_script",f"{bifrost_config_and_data_path}/post.sh",
            "--run_metadata", f"{bifrost_config_and_data_path}/run_metadata.tsv",
            "--reads_folder", f"{bifrost_config_and_data_path}/samples",
            "--run_name", "bifrost_test",
            "--run_type", "test",
            "--componentsubset", "bifrost_min_read_check_v2_2_8,bifrost_whats_my_species_v2_2_11__171019,bifrost_cge_mlst_v2_2_6__210314",
            "--samplesubset", "S1"
        ]
        launcher.main(args=test_args)
        #clear collection
        assert os.path.isfile(f"{self.test_dir}/{self.component_name}/run_script.sh")
        assert os.path.isfile(f"{self.test_dir}/{self.component_name}/run.yaml")
        assert os.path.isfile(f"{self.test_dir}/{self.component_name}/samples.yaml")
        #shutil.rmtree(self.test_dir)
        #assert not os.path.isdir(f"{self.test_dir}/{self.component_name}")


