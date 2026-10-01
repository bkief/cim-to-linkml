from pathlib import Path
import pytest

from cim_to_linkml.generator import (
    generate_schema,
    _map_primitive_data_type,
    _is_slot_required,
    _is_slot_multivalued,
    _generate_curie,
)
from cim_to_linkml.read_rdf import read_rdf_project
import cim_to_linkml.linkml_model as linkml_model
import cim_to_linkml.uml_model as uml_model


class TestGeneratorHelpers:
    def test_map_primitive_data_type(self):
        assert _map_primitive_data_type("String") == "string"
        assert _map_primitive_data_type("Float") == "float"
        assert _map_primitive_data_type("Integer") == "integer"
        assert _map_primitive_data_type("Boolean") == "boolean"
        assert _map_primitive_data_type("DateTime") == "datetime"
        assert _map_primitive_data_type("Date") == "date"
        assert _map_primitive_data_type("Time") == "time"
        assert _map_primitive_data_type("Decimal") == "decimal"
        assert _map_primitive_data_type("Duration") == "string"
        assert _map_primitive_data_type("MonthDay") == "string"

    def test_map_primitive_data_type_invalid(self):
        with pytest.raises(TypeError, match="is not a CIM Primitive"):
            _map_primitive_data_type("NonExistentPrimitiveType")

    def test_is_slot_required(self):
        assert _is_slot_required(1) is True
        assert _is_slot_required(2) is True
        assert _is_slot_required("*") is True
        assert _is_slot_required(0) is False

    def test_is_slot_multivalued(self):
        assert _is_slot_multivalued("*") is True
        assert _is_slot_multivalued(2) is True
        assert _is_slot_multivalued(1) is False
        assert _is_slot_multivalued(0) is False

    def test_generate_curie(self):
        assert _generate_curie("Substation", "cim") == "cim:Substation"
        assert _generate_curie("ACLineSegment.r", "cim") == "cim:ACLineSegment.r"


class TestSchemaGeneration:
    def test_generate_schema_from_ttl(self, test_data_dir: Path):
        project = read_rdf_project(str(test_data_dir / "simple_substation.ttl"))
        pkg = project.packages.by_qualified_name["Core"]
        classes = project.classes.by_package.get(pkg.id, [])

        schema = generate_schema(pkg, classes, project)
        assert isinstance(schema, linkml_model.Schema)
        assert schema.name == "Core"
        assert schema.metamodel_version == "1.7.0"
        assert schema.imports is not None and "linkml:types" in schema.imports
        assert schema.prefixes is not None and "cim" in schema.prefixes
        assert schema.default_prefix == "cim"

        # Check classes
        assert schema.classes is not None
        assert "Substation" in schema.classes
        assert "Equipment" in schema.classes

        substation_cls = schema.classes["Substation"]
        assert substation_cls.class_uri == "cim:Substation"
        assert substation_cls.attributes is not None
        assert "name" in substation_cls.attributes

        sub_name = substation_cls.attributes["name"]
        assert sub_name.range == "string"
        assert sub_name.required is True
        assert sub_name.multivalued is False

    def test_generate_schema_from_rdfs_distribution_network(self, test_data_dir: Path):
        project = read_rdf_project(str(test_data_dir / "DistributionNetwork.rdfs"))
        wires_pkg = project.packages.by_qualified_name["Wires"]
        classes = project.classes.by_package.get(wires_pkg.id, [])

        schema = generate_schema(wires_pkg, classes, project)
        assert isinstance(schema, linkml_model.Schema)
        assert schema.name == "Wires"

        # ACLineSegment should be present with inheritance
        assert schema.classes is not None
        assert "ACLineSegment" in schema.classes
        ac_line = schema.classes["ACLineSegment"]
        assert ac_line.is_a == "Conductor"

    def test_generate_schema_from_cgmes_topology_owl(self, test_data_dir: Path):
        project = read_rdf_project(str(test_data_dir / "CGMES_Topology.owl"))
        model_pkg = project.packages.by_qualified_name["Model"]
        classes = project.classes.by_package.get(model_pkg.id, [])

        schema = generate_schema(model_pkg, classes, project)
        assert isinstance(schema, linkml_model.Schema)
        assert schema.classes is not None
        assert "TopologicalNode" in schema.classes
        assert "Terminal" in schema.classes

        topo_node = schema.classes["TopologicalNode"]
        assert topo_node.class_uri == "cim:TopologicalNode"

    def test_generate_schema_with_enums(self, test_data_dir: Path):
        project = read_rdf_project(str(test_data_dir / "SampleProfile.owl"))
        model_pkg = project.packages.by_qualified_name["Model"]
        classes = project.classes.by_package.get(model_pkg.id, [])

        schema = generate_schema(model_pkg, classes, project)
        assert isinstance(schema, linkml_model.Schema)
        assert schema.classes is not None
        assert len(schema.classes) > 0
        if schema.enums:
            for enum_name, enum_obj in schema.enums.items():
                assert enum_obj.name == enum_name
                assert enum_obj.enum_uri.startswith("cim:")
