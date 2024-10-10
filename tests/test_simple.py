from argparse import Namespace
import pytest
import tempfile
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
from pathlib import Path


bifrost_install_dir = os.environ['BIFROST_INSTALL_DIR']
bifrost_config_and_data_path = Path(f"{bifrost_install_dir}/bifrost/test_data")

test_dir = Path(f"{bifrost_config_and_data_path}/output/test__run_launcher/")
test_dir.mkdir(mode=0o755,parents=True,exist_ok=True)


@pytest.fixture
def test_connection():
    assert datahandling.has_a_database_connection()
    assert "TEST" in os.environ['BIFROST_DB_KEY'].upper()  # A very basic piece of protection ensuring the word test is in the DB

@pytest.fixture
def db():
    client = pymongo.MongoClient(os.environ['BIFROST_DB_KEY'])
    yield client.get_database()
    client.close()

@pytest.fixture
def initialized_launcher():
    launcher.initialize()

@pytest.fixture
def use_collection(db):
    '''Factory fixture returning a function to clean collections used in the test, and take care of their clean up after use.'''
    created_collections = []
    def _collection(name: str):
        created_collections.append(name)
        db.drop_collection(name)
        return db[name]
    yield _collection
    # Clean up the used collections
    for name in created_collections:
        db.drop_collection(name)

@pytest.fixture(scope="module")
def clean_dir(request):
    parent_dir = getattr(request.module, "test_dir", None)
    newpath = tempfile.mkdtemp(dir=parent_dir)
    yield newpath
    shutil.rmtree(newpath)

class TestBifrostRunLauncher:
    component_name = "run_launcher__v2.3.0"

    @pytest.fixture
    def sample_args(self, clean_dir):
        return [
            "--outdir", f"{clean_dir}/{self.component_name}",
            "--pre_script", f"{bifrost_config_and_data_path}/pre.sh",
            "--per_sample_script", f"{bifrost_config_and_data_path}/per_sample.sh",
            "--post_script",f"{bifrost_config_and_data_path}/post.sh",
            "--run_metadata", f"{bifrost_config_and_data_path}/run_metadata.tsv",
            "--reads_folder", f"{bifrost_config_and_data_path}/samples",
            "--run_name", "bifrost_test",
            "--run_type", "test",
            "--component_subset", "bifrost_min_read_check_v2_2_8,bifrost_whats_my_species_v2_2_11__171019,bifrost_cge_mlst_v2_2_6__210314",
            "--sample_subset", "S1"
            ]

    def test_info(self):
        launcher.run_pipeline(["--info"])

    def test_help(self):
        launcher.run_pipeline(["--help"])

    def test_pipeline(self, use_collection, clean_dir, sample_args):
        use_collection("samples")
        use_collection("runs")
        use_collection("components")

        bifrost_config_and_data_path = "/bifrost/test_data"
        launcher.main(args=sample_args)
        assert os.path.isfile(f"{clean_dir}/{self.component_name}/run_script.sh")
        assert os.path.isfile(f"{clean_dir}/{self.component_name}/run.yaml")
        assert os.path.isfile(f"{clean_dir}/{self.component_name}/samples.yaml")

    def test_pipeline_run_twice(self, use_collection, clean_dir, sample_args):
        samples = use_collection("samples")
        runs = use_collection("runs")
        use_collection("components")

        launcher.main(args=sample_args)
        samples_dump1 = list(samples.find({}))
        runs_dump1 = list(runs.find({}))
        launcher.main(args=sample_args)
        samples_dump2 = list(samples.find({}))
        runs_dump2 = list(runs.find({}))
        assert os.path.isfile(f"{clean_dir}/{self.component_name}/run_script.sh")
        assert os.path.isfile(f"{clean_dir}/{self.component_name}/run.yaml")
        assert os.path.isfile(f"{clean_dir}/{self.component_name}/samples.yaml")
        assert samples_dump1 != samples_dump2
        assert runs_dump1 != runs_dump2

    def test_pipeline_run_twice_with_unique_indexes(self, use_collection, clean_dir, sample_args):
        samples = use_collection("samples")
        runs = use_collection("runs")
        components = use_collection("components")
        index_name = database_interface.index_field("component","name",unique=True)
        assert index_name in database_interface.get_index("component")
        index_name = database_interface.index_field("sample","name",unique=True)
        assert index_name in database_interface.get_index("sample")
        index_name = database_interface.index_field("run","name",unique=True)
        assert index_name in database_interface.get_index("run")

        launcher.main(args=sample_args)
        samples_dump1 = list(samples.find({}))
        runs_dump1 = list(runs.find({}))
        launcher.main(args=sample_args)
        samples_dump2 = list(samples.find({}))
        runs_dump2 = list(runs.find({}))
        assert os.path.isfile(f"{clean_dir}/{self.component_name}/run_script.sh")
        assert os.path.isfile(f"{clean_dir}/{self.component_name}/run.yaml")
        assert os.path.isfile(f"{clean_dir}/{self.component_name}/samples.yaml")
        assert samples_dump1 == samples_dump2
        assert runs_dump1 == runs_dump2
