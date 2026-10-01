"""The same CIM release exported as QEA, XMI 1.1 and XMI 2.1 should yield equivalent models."""

import sqlite3
from pathlib import Path

import pytest

import cim_to_linkml.uml_model as uml_model
from cim_to_linkml.generator import generate_class, generate_enum_class
from cim_to_linkml.parser import parse_uml_project
from cim_to_linkml.read import read_uml_project
from cim_to_linkml.read_xmi import read_xmi_project

CIM17_STEM = "cim17/iec61970cim17v40_iec61968cim13v13b_iec62325cim03v17b_CIM100.1.1.1"


def _load(path: Path) -> uml_model.Project:
    if path.suffix == ".qea":
        with sqlite3.connect(path) as conn:
            return parse_uml_project(*read_uml_project(conn))
    return parse_uml_project(*read_xmi_project(str(path)))


@pytest.fixture(scope="module", params=[".qea", "_XMI11.xmi", "_XMI21.xmi"])
def cim17_project(request, test_data_dir: Path, decompress_test_data) -> uml_model.Project:
    path = test_data_dir / (CIM17_STEM + request.param)
    if not path.exists():
        pytest.skip(f"{path.name} not present")
    return _load(path)


class TestCim17Consistency:
    def test_class_count(self, cim17_project: uml_model.Project):
        # EA diagram notes, text and boundaries must not be picked up as classes.
        assert 1945 <= len(cim17_project.classes.by_id) <= 1950

    def test_generalizations(self, cim17_project: uml_model.Project):
        ac_line = generate_class(cim17_project.classes.by_name["ACLineSegment"], cim17_project)
        assert ac_line.is_a == "Conductor"

    def test_cim_version_annotation(self, cim17_project: uml_model.Project):
        ac_line = generate_class(cim17_project.classes.by_name["ACLineSegment"], cim17_project)
        assert ac_line.annotations is not None
        assert ac_line.annotations["cim_version"] == "IEC61970CIM17v40"

    def test_enumeration_literals(self, cim17_project: uml_model.Project):
        phase_code = cim17_project.classes.by_name["PhaseCode"]
        assert phase_code.stereotype == uml_model.ClassStereotype.ENUMERATION
        enum = generate_enum_class(phase_code, cim17_project)
        assert "ABCN" in enum.permissible_values

    def test_package_documentation_belongs_to_package(self, cim17_project: uml_model.Project):
        core = cim17_project.packages.by_qualified_name["Model.TC57CIM.IEC61970.Base.Core"]
        assert core.notes is not None and core.notes.startswith("Contains the core PowerSystemResource")

    def test_nested_class_is_present(self, cim17_project: uml_model.Project):
        end_device = cim17_project.classes.by_name["EndDevice"]
        assert cim17_project.packages.get_qualified_name(end_device.package).endswith("IEC61968.Metering")


def test_cim18_qea_parses(test_data_dir: Path, decompress_test_data):
    # CIM18 contains `Abstraction' connectors, which used to crash parsing.
    path = next((test_data_dir / "cim18").glob("*.qea"), None)
    if path is None:
        pytest.skip("CIM18 QEA not present")
    project = _load(path)
    assert "Model.CIM" in project.packages.by_qualified_name
