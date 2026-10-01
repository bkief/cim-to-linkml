import os
from typing import Optional

import yaml

import cim_to_linkml.linkml_model as linkml_model


# The libyaml based emitter is several times faster, which matters since schemas can be megabytes large.
Dumper = getattr(yaml, "CDumper", yaml.Dumper)


def init_yaml_serializer():
    yaml.add_representer(type(None), represent_none, Dumper=Dumper)
    yaml.add_representer(linkml_model.Slot, represent_linkml_slot, Dumper=Dumper)
    yaml.add_representer(linkml_model.Class, represent_linkml_class, Dumper=Dumper)
    yaml.add_representer(linkml_model.Enum, represent_linkml_enum, Dumper=Dumper)
    yaml.add_representer(linkml_model.PermissibleValue, represent_linkml_permissible_value, Dumper=Dumper)
    yaml.add_representer(linkml_model.Schema, represent_linkml_schema, Dumper=Dumper)


def represent_none(self, _):
    """Replace `null` with the empty string."""

    return self.represent_scalar("tag:yaml.org,2002:null", "")


def represent_linkml_schema(dumper, data):
    d = {k: v for k, v in data._asdict().items() if v not in [[], {}, None]}

    return dumper.represent_dict(d)


def represent_linkml_permissible_value(dumper, data):
    d = {k: v for k, v in data._asdict().items() if v is not None}

    return dumper.represent_dict(d)


def represent_linkml_enum(dumper, data):
    d = {k: v for k, v in data._asdict().items() if k not in ["name"] if v not in [[], {}, None]}

    return dumper.represent_dict(d)


def represent_linkml_class(dumper, data):
    d = {k: v for k, v in data._asdict().items() if k not in ["name"] if v not in [[], {}, None]}

    return dumper.represent_dict(d)


def represent_linkml_slot(dumper, data):
    d = {k: v for k, v in data._asdict().items() if k not in ["name"] if v not in [[], {}, None]}

    return dumper.represent_dict(d)


def write_schema(schema: linkml_model.Schema, out_file: os.PathLike | str) -> None:
    with open(out_file, "w", encoding="utf-8") as f:
        yaml.dump(
            schema, f, Dumper=Dumper, indent=2, default_flow_style=False, sort_keys=False
        )
