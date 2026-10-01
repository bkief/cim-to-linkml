from pathlib import Path
import yaml
import pytest

from cim_to_linkml.writer import init_yaml_serializer, write_schema
import cim_to_linkml.linkml_model as linkml_model


class TestWriter:
    @pytest.fixture(autouse=True)
    def setup_serializer(self):
        init_yaml_serializer()

    def test_write_schema(self, tmp_path: Path):
        slot = linkml_model.Slot(
            name="name",
            slot_uri="cim:Substation.name",
            range="string",
            required=True,
            multivalued=False,
            description="The name of the substation",
        )
        cls = linkml_model.Class(
            name="Substation",
            class_uri="cim:Substation",
            description="A substation",
            attributes={"name": slot},
            from_schema="https://cim.ucaiug.io/ns#Core",
        )
        enum_pv = linkml_model.PermissibleValue(meaning="cim:PhaseCode.A")
        enum_obj = linkml_model.Enum(
            name="PhaseCode",
            enum_uri="cim:PhaseCode",
            description="Phase code",
            permissible_values={"A": {"meaning": enum_pv}},
        )
        schema = linkml_model.Schema(
            id="https://cim.ucaiug.io/ns#Core",
            name="Core",
            title="Core Schema",
            description="Core CIM Package",
            metamodel_version="1.7.0",
            prefixes={"cim": "https://cim.ucaiug.io/ns#", "linkml": "https://w3id.org/linkml/"},
            default_prefix="cim",
            default_range="string",
            classes={"Substation": cls},
            enums={"PhaseCode": enum_obj},
        )

        out_file = tmp_path / "Core.yml"
        write_schema(schema, str(out_file))

        assert out_file.exists()
        assert out_file.stat().st_size > 0

        # Validate that the dumped YAML is loadable and has correct keys
        with open(out_file, "r") as f:
            data = yaml.safe_load(f)

        assert data["id"] == "https://cim.ucaiug.io/ns#Core"
        assert data["name"] == "Core"
        assert "Substation" in data["classes"]
        assert data["classes"]["Substation"]["class_uri"] == "cim:Substation"
        assert "name" in data["classes"]["Substation"]["attributes"]
        assert data["classes"]["Substation"]["attributes"]["name"]["range"] == "string"
        assert "PhaseCode" in data["enums"]
