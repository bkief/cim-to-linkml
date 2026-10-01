from pathlib import Path
import pytest
import rdflib
from rdflib.namespace import OWL

from cim_to_linkml.read_rdf import read_rdf_project, _get_local_name
import cim_to_linkml.uml_model as uml_model
from tests.conftest import OWL_FILES, RDFS_FILES, TTL_FILES


class TestReadRdfHelper:
    def test_get_local_name_hash(self):
        assert _get_local_name("http://iec.ch/TC57/CIM100#Substation") == "Substation"

    def test_get_local_name_slash(self):
        assert _get_local_name("http://iec.ch/TC57/CIM100/Substation") == "Substation"


class TestReadRdfModels:
    @pytest.mark.parametrize("owl_filename", OWL_FILES)
    def test_read_owl_models(self, test_data_dir: Path, owl_filename: str):
        filepath = test_data_dir / owl_filename
        assert filepath.exists(), f"File {owl_filename} does not exist in {test_data_dir}"

        project = read_rdf_project(str(filepath))
        assert isinstance(project, uml_model.Project)
        assert len(project.packages.by_id) >= 1
        assert len(project.classes.by_id) > 0
        assert len(project.relations.by_id) >= 0

        # Verify no blank nodes exist in class IDs
        for cls in project.classes.by_id.values():
            assert not str(cls.id).startswith("N"), f"Blank node found as class ID: {cls.id}"
            assert cls.id != str(OWL.Thing), "owl:Thing should be excluded from classes"
            assert cls.name, "Class name must not be empty"

    @pytest.mark.parametrize("rdfs_filename", RDFS_FILES)
    def test_read_rdfs_models(self, test_data_dir: Path, rdfs_filename: str):
        filepath = test_data_dir / rdfs_filename
        assert filepath.exists(), f"File {rdfs_filename} does not exist in {test_data_dir}"

        project = read_rdf_project(str(filepath))
        assert isinstance(project, uml_model.Project)
        assert len(project.packages.by_id) >= 1
        assert len(project.classes.by_id) > 0

        # Check that relations only connect valid classes
        class_ids = set(project.classes.by_id.keys())
        for rel in project.relations.by_id.values():
            assert rel.source_class in class_ids, f"Relation source {rel.source_class} not in classes"
            assert rel.dest_class in class_ids, f"Relation dest {rel.dest_class} not in classes"

    @pytest.mark.parametrize("ttl_filename", TTL_FILES)
    def test_read_ttl_models(self, test_data_dir: Path, ttl_filename: str):
        filepath = test_data_dir / ttl_filename
        assert filepath.exists()

        project = read_rdf_project(str(filepath))
        assert isinstance(project, uml_model.Project)
        assert len(project.classes.by_id) > 0

    def test_distribution_network_rdfs_details(self, test_data_dir: Path):
        filepath = test_data_dir / "DistributionNetwork.rdfs"
        project = read_rdf_project(str(filepath))

        # Check packages
        pkg_names = set(project.packages.by_qualified_name.keys())
        assert "Wires" in pkg_names
        assert "Core" in pkg_names

        # Check ACLineSegment class in Wires package
        ac_line = project.classes.by_name.get("ACLineSegment")
        assert ac_line is not None

        # Check PerLengthSequenceImpedance class attributes
        plsi = project.classes.by_name.get("PerLengthSequenceImpedance")
        assert plsi is not None
        attr_names = {a.name for a in plsi.attributes}
        assert "r" in attr_names
        assert "x" in attr_names

        # Check generalization: ACLineSegment is a Conductor
        rels = project.relations.by_source_class.get(ac_line.id, [])
        gen_rels = [r for r in rels if r.type == uml_model.RelationType.GENERALIZATION]
        assert len(gen_rels) >= 1

    def test_cgmes_topology_owl_details(self, test_data_dir: Path):
        filepath = test_data_dir / "CGMES_Topology.owl"
        project = read_rdf_project(str(filepath))

        # Check TopologicalNode class
        topo_node = project.classes.by_name.get("TopologicalNode")
        assert topo_node is not None
        assert topo_node.name == "TopologicalNode"

        # Check Terminal relation
        terminal = project.classes.by_name.get("Terminal")
        assert terminal is not None

    def test_read_rdf_invalid_file(self, tmp_path: Path):
        corrupt_file = tmp_path / "corrupt.rdf"
        corrupt_file.write_text("<<<INVALID XML CONTENT>>>")
        with pytest.raises(Exception):
            read_rdf_project(str(corrupt_file))

    def test_rdfs_association_ends_are_paired(self, test_data_dir: Path):
        # Each RDFS association end is a property linked to its counterpart via `cims:inverseRoleName'.
        # They must form one relation, with each end's own name and multiplicity, and no invented slots.
        from cim_to_linkml.generator import generate_class

        project = read_rdf_project(str(test_data_dir / "CGMES_Topology_RDFS2020.rdfs"))
        terminal = generate_class(project.classes.by_name["Terminal"], project)
        topo_node = generate_class(project.classes.by_name["TopologicalNode"], project)
        assert terminal.attributes is not None and topo_node.attributes is not None

        assert set(terminal.attributes) == {"TopologicalNode"}
        assert terminal.attributes["TopologicalNode"].range == "TopologicalNode"
        assert not terminal.attributes["TopologicalNode"].multivalued

        assert "TopologicalNode" not in topo_node.attributes
        assert topo_node.attributes["Terminal"].range == "Terminal"
        assert topo_node.attributes["Terminal"].multivalued
