import lzma
import shutil
from pathlib import Path
import pytest
from click.testing import CliRunner

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
TEST_DATA_DIR = TESTS_DIR / "data" if (TESTS_DIR / "data").exists() else PROJECT_ROOT / "test" / "data"
DATA_DIR = PROJECT_ROOT / "data" if (PROJECT_ROOT / "data").exists() and any((PROJECT_ROOT / "data").iterdir()) else TEST_DATA_DIR

OWL_FILES = [
    "cpsm2007.owl",
    "SampleProfile.owl",
    "CGMES_Topology.owl",
    "CGMES_EquipmentBoundary.owl",
]

RDFS_FILES = [
    "DistributionNetwork.rdfs",
    "CGMES_Topology_RDFS2020.rdfs",
    "CGMES_EquipmentBoundary_RDFS2020.rdfs",
    "CGMES_GeographicalLocation_RDFS2020.rdfs",
    "DMP_profile_IEC61970-457.rdfs",
]

TTL_FILES = [
    "simple_substation.ttl",
]


@pytest.fixture(scope="session", autouse=True)
def decompress_test_data() -> None:
    """Expand the committed *.xz test models next to themselves (once)."""
    for xz_path in TEST_DATA_DIR.rglob("*.xz"):
        target = xz_path.with_suffix("")
        if target.exists():
            continue
        tmp = target.with_name(target.name + ".part")
        with lzma.open(xz_path, "rb") as src, open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst)
        tmp.replace(target)


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    return TEST_DATA_DIR


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    out_dir = tmp_path / "schemas"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
