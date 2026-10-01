from pathlib import Path
import pytest
from click.testing import CliRunner
import yaml

from cim_to_linkml.main import _resolve_package, cli
from cim_to_linkml.uml_model import is_package_or_subpackage


class TestCLI:
    def test_cli_help(self, cli_runner: CliRunner):
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Generates LinkML schemas" in result.output
        assert "--package" in result.output
        assert "--single-schema" in result.output
        assert "--ignore-subpackages" in result.output
        assert "--output-dir" in result.output

    def test_cli_rdfs_file_auto_package(
        self, cli_runner: CliRunner, test_data_dir: Path, temp_output_dir: Path
    ):
        rdfs_file = test_data_dir / "CGMES_Topology_RDFS2020.rdfs"
        result = cli_runner.invoke(
            cli, [str(rdfs_file), "-o", str(temp_output_dir)]
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"

        out_yaml = temp_output_dir / "TopologyProfile.yml"
        assert out_yaml.exists()
        assert out_yaml.stat().st_size > 0

        with open(out_yaml, "r") as f:
            data = yaml.safe_load(f)
        assert data["name"] == "TopologyProfile"
        assert "TopologicalNode" in data["classes"]

    def test_cli_rdfs_file_explicit_package(
        self, cli_runner: CliRunner, test_data_dir: Path, temp_output_dir: Path
    ):
        rdfs_file = test_data_dir / "DistributionNetwork.rdfs"
        result = cli_runner.invoke(
            cli, [str(rdfs_file), "-p", "Wires", "-o", str(temp_output_dir)]
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"

        out_yaml = temp_output_dir / "Wires.yml"
        assert out_yaml.exists()
        with open(out_yaml, "r") as f:
            data = yaml.safe_load(f)
        assert data["name"] == "Wires"
        assert "ACLineSegment" in data["classes"]

    def test_cli_owl_file(
        self, cli_runner: CliRunner, test_data_dir: Path, temp_output_dir: Path
    ):
        owl_file = test_data_dir / "CGMES_Topology.owl"
        result = cli_runner.invoke(
            cli, [str(owl_file), "-p", "Model", "-o", str(temp_output_dir)]
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"

        out_yaml = temp_output_dir / "Model.yml"
        assert out_yaml.exists()
        with open(out_yaml, "r") as f:
            data = yaml.safe_load(f)
        assert "TopologicalNode" in data["classes"]

    def test_cli_ttl_file(
        self, cli_runner: CliRunner, test_data_dir: Path, temp_output_dir: Path
    ):
        ttl_file = test_data_dir / "simple_substation.ttl"
        result = cli_runner.invoke(
            cli, [str(ttl_file), "-p", "Core", "-o", str(temp_output_dir)]
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"

        out_yaml = temp_output_dir / "Core.yml"
        assert out_yaml.exists()
        with open(out_yaml, "r") as f:
            data = yaml.safe_load(f)
        assert "Substation" in data["classes"]

    def test_cli_xmi_file(
        self, cli_runner: CliRunner, data_dir: Path, temp_output_dir: Path
    ):
        xmi_file = next(data_dir.rglob("*_XMI11.xmi"), None)
        if not xmi_file or not xmi_file.exists():
            pytest.skip("XMI 1.1 file not present")

        from cim_to_linkml.read_xmi import read_xmi_project
        from cim_to_linkml.parser import parse_uml_project
        proj = parse_uml_project(*read_xmi_project(str(xmi_file)))
        # Pick a package from the model
        pkg_name = next(iter(proj.packages.by_qualified_name.keys()))

        result = cli_runner.invoke(
            cli,
            [
                str(xmi_file),
                "-p",
                pkg_name,
                "-o",
                str(temp_output_dir),
            ],
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"

    def test_cli_nonexistent_file(self, cli_runner: CliRunner, tmp_path: Path):
        nonexistent = tmp_path / "does_not_exist.owl"
        result = cli_runner.invoke(cli, [str(nonexistent)])
        assert result.exit_code != 0

    def test_cli_unsupported_extension(
        self, cli_runner: CliRunner, tmp_path: Path
    ):
        bad_file = tmp_path / "model.unsupported"
        bad_file.write_text("content")
        result = cli_runner.invoke(cli, [str(bad_file)])
        assert result.exit_code == 1
        assert "Unsupported file format" in result.output

    def test_cli_unknown_package_lists_available(
        self, cli_runner: CliRunner, test_data_dir: Path
    ):
        rdfs_file = test_data_dir / "DistributionNetwork.rdfs"
        result = cli_runner.invoke(
            cli, [str(rdfs_file), "-p", "NonExistentPackage"]
        )
        assert result.exit_code == 1
        assert "Ignoring unknown package: `NonExistentPackage'" in result.output
        assert "Available packages:" in result.output
        assert "'Wires'" in result.output


class TestPackageResolution:
    QNAMES = ["Model", "Model.TC57CIM", "Model.TC57CIM.IEC61970", "Model.TC57CIM.IEC61970.Base.Core"]

    def test_exact_match(self):
        assert _resolve_package("Model.TC57CIM", self.QNAMES) == "Model.TC57CIM"

    def test_suffix_match_for_ea_model_root(self):
        # Enterprise Architect exports nest everything under a `Model' root package.
        assert _resolve_package("TC57CIM", self.QNAMES) == "Model.TC57CIM"
        assert _resolve_package("IEC61970.Base.Core", self.QNAMES) == "Model.TC57CIM.IEC61970.Base.Core"

    def test_default_falls_back_to_single_package(self):
        assert _resolve_package("TC57CIM", ["TopologyProfile"]) == "TopologyProfile"

    def test_unknown(self):
        assert _resolve_package("Wires", self.QNAMES) is None

    def test_ambiguous_suffix_is_rejected(self):
        assert _resolve_package("Assets", ["A.Assets", "B.Assets"]) is None


def test_is_package_or_subpackage():
    assert is_package_or_subpackage("TC57CIM.Base.Core", "TC57CIM.Base")
    assert is_package_or_subpackage("TC57CIM.Base", "TC57CIM.Base")
    assert not is_package_or_subpackage("TC57CIM.BaseExt", "TC57CIM.Base")
