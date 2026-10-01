from pathlib import Path
import pytest

from cim_to_linkml.read_xmi import read_xmi_project
from cim_to_linkml.parser import parse_uml_project
import cim_to_linkml.uml_model as uml_model


class TestReadXmi:
    def test_read_xmi_11(self, data_dir: Path):
        xmi_file = next(data_dir.rglob("*_XMI11.xmi"), None)
        if not xmi_file or not xmi_file.exists():
            pytest.skip("XMI 1.1 sample file not found in data_dir")

        pkg_rows, class_rows, rel_rows = read_xmi_project(str(xmi_file))
        assert len(pkg_rows) > 0
        assert len(class_rows) > 0
        assert len(rel_rows) > 0

        project = parse_uml_project(pkg_rows, class_rows, rel_rows)
        assert isinstance(project, uml_model.Project)
        assert len(project.packages.by_id) > 0
        assert len(project.classes.by_id) > 0
        assert len(project.relations.by_id) > 0

        # Check for expected packages
        pkg_names = set(project.packages.by_qualified_name.keys())
        assert any("Core" in name or "Wires" in name or "TC57CIM" in name for name in pkg_names)

    def test_read_xmi_21(self, data_dir: Path):
        xmi_file = next(data_dir.rglob("*_XMI21.xmi"), None)
        if not xmi_file or not xmi_file.exists():
            pytest.skip("XMI 2.1 sample file not found in data_dir")

        pkg_rows, class_rows, rel_rows = read_xmi_project(str(xmi_file))
        assert len(pkg_rows) > 0
        assert len(class_rows) > 0
        assert len(rel_rows) > 0

        project = parse_uml_project(pkg_rows, class_rows, rel_rows)
        assert isinstance(project, uml_model.Project)
        assert len(project.packages.by_id) > 0
        assert len(project.classes.by_id) > 0
        assert len(project.relations.by_id) > 0

    def test_read_xmi_arbitrary_xml(self, tmp_path: Path):
        dummy_xml = tmp_path / "dummy.xml"
        dummy_xml.write_text("<root><child>value</child></root>")
        pkgs, classes, rels = read_xmi_project(str(dummy_xml))
        assert list(pkgs) == []
        assert list(classes) == []
        assert list(rels) == []

    def test_read_xmi_nonexistent_file(self, tmp_path: Path):
        nonexistent = tmp_path / "missing.xmi"
        with pytest.raises(Exception):
            read_xmi_project(str(nonexistent))
