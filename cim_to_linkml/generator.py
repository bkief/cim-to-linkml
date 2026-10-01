import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional
from urllib.parse import quote

import cim_to_linkml.linkml_model as linkml_model
import cim_to_linkml.uml_model as uml_model

LINKML_METAMODEL_VERSION = "1.7.0"
GITHUB_BASE_URL = "https://github.com/"
GITHUB_REPO_URL = "https://github.com/bartkl/cim-to-linkml"

logger = logging.getLogger(__name__)


def generate_schema(
    uml_package: uml_model.Package, uml_classes: list[uml_model.Class], uml_project: uml_model.Project
) -> linkml_model.Schema:
    classes = {}
    enums = {}

    for uml_class in uml_classes:
        _classes, _enums = _generate_elements_for_class(uml_class, uml_project)
        classes.update(_classes)
        enums.update(_enums)

    schema = linkml_model.Schema(
        id=_generate_schema_id(uml_package, uml_project),
        name=uml_project.packages.get_qualified_name(uml_package.id),
        title=uml_package.name,
        description=uml_package.notes,
        contributors=["github:bartkl"],
        created_by=GITHUB_REPO_URL,
        generation_date=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        license="https://www.apache.org/licenses/LICENSE-2.0.txt",
        metamodel_version=LINKML_METAMODEL_VERSION,
        imports=["linkml:types"],
        prefixes={
            "linkml": "https://w3id.org/linkml/",
            "github": "https://github.com/",
            linkml_model.CIM_PREFIX: linkml_model.CIM_BASE_URI,
        },
        default_curi_maps=["semweb_context"],
        default_prefix=linkml_model.CIM_PREFIX,
        default_range="string",
        classes=classes,
        enums=enums,
    )

    return schema


def _generate_elements_for_class(
    uml_class: uml_model.Class, uml_project: uml_model.Project, results: tuple[dict, dict] | None = None
) -> tuple[dict, dict]:
    """Generates the class or enum and its dependencies.

    This method does the heavy lifting. It recursively traverses all dependencies
    of the given UML class, e.g. its ancestor classes, associated classes and
    enum types, etc. Every class dependency is either a class or enum class, and
    once generated to LinkML elements they are accumulated and ultimately returend
    in `results`
    """

    if results is None:
        results = {}, {}

    match uml_class.stereotype:
        case uml_model.ClassStereotype.PRIMITIVE:
            # TODO: Log.
            return results
        case uml_model.ClassStereotype.ENUMERATION:
            enum = generate_enum_class(uml_class, uml_project)
            results[1][uml_class.name] = enum
        case uml_model.ClassStereotype.CIMDATATYPE:
            class_ = generate_class(uml_class, uml_project)
            results[0][uml_class.name] = class_
        case None | _:
            class_ = generate_class(uml_class, uml_project)
            results[0][uml_class.name] = class_

    uml_dep_classes = tuple()  # TODO: Now duplicates can be stored. Improve this.

    uml_super_class = _get_super_class(uml_class, uml_project)
    if uml_super_class:
        uml_dep_classes = uml_dep_classes + (uml_super_class,)

    uml_dep_classes = (
        uml_dep_classes + _get_attribute_types(uml_class, uml_project) + _get_related_classes(uml_class, uml_project)
    )

    for uml_dep_class in uml_dep_classes:
        if uml_dep_class.name in results[0]:
            continue
        results = _generate_elements_for_class(uml_dep_class, uml_project, results)
    return results


@lru_cache(maxsize=1942)
def generate_class(uml_class: uml_model.Class, uml_project: uml_model.Project) -> linkml_model.Class:
    super_class = _get_super_class(uml_class, uml_project)
    package = uml_project.packages.by_id[uml_class.package]

    attr_slots = tuple(
        slot
        for uml_attr in uml_class.attributes
        if (slot := generate_slot_from_attribute(uml_attr, uml_class, uml_project))
    )

    from_relation_slots = tuple(
        slot
        for rel in uml_project.relations.by_source_class.get(uml_class.id, [])
        if rel and rel.type != uml_model.RelationType.GENERALIZATION
        if (slot := generate_slot_from_relation(rel, uml_project, "source->dest"))
    )

    to_relation_slots = tuple(
        slot
        for rel in uml_project.relations.by_dest_class.get(uml_class.id, [])
        if rel and rel.type != uml_model.RelationType.GENERALIZATION
        if rel.bidirectional
        if (slot := generate_slot_from_relation(rel, uml_project, "dest->source"))
    )

    annotations = {}
    if uml_class.stereotype == uml_model.ClassStereotype.CIMDATATYPE:
        annotations["represents_cim_data_type"] = True

    version = _get_package_version(uml_class.package, uml_project)
    if version:
        annotations["cim_version"] = version

    spec = _get_package_specification(uml_class.package, uml_project)
    if spec:
        annotations["cim_specification"] = spec

    class_ = linkml_model.Class(
        name=uml_class.name,
        class_uri=_generate_curie(uml_class.name, linkml_model.CIM_PREFIX),
        is_a=super_class.name if super_class else None,
        annotations=annotations,
        description=uml_class.note,
        attributes={slot.name: slot for slot in (attr_slots + from_relation_slots + to_relation_slots)} or None,
        from_schema=_generate_schema_id(package, uml_project),
    )

    return class_


@lru_cache(maxsize=1942)
def generate_enum_class(uml_enum: uml_model.Class, uml_project: uml_model.Project) -> linkml_model.Enum:
    assert uml_enum.stereotype == uml_model.ClassStereotype.ENUMERATION
    package = uml_project.packages.by_id[uml_enum.package]

    return linkml_model.Enum(
        name=uml_enum.name,
        enum_uri=_generate_curie(uml_enum.name, linkml_model.CIM_PREFIX),
        description=uml_enum.note,
        permissible_values={
            uml_enum_val.name: linkml_model.PermissibleValue(
                meaning=_generate_curie(f"{uml_enum.name}.{uml_enum_val.name}", linkml_model.CIM_PREFIX)
            )._asdict()
            for uml_enum_val in uml_enum.attributes
        },
        from_schema=_generate_schema_id(package, uml_project),
    )


def generate_slot_from_attribute(
    uml_attr: uml_model.Attribute, uml_class: uml_model.Class, uml_project: uml_model.Project
) -> linkml_model.Slot:
    type_name = uml_attr.type or "String"
    type_class = uml_project.classes.by_name.get(type_name)
    if type_class and type_class.stereotype == uml_model.ClassStereotype.PRIMITIVE:
        range_ = _map_primitive_data_type(type_name)
    elif type_class:
        range_ = type_class.name
    else:
        try:
            range_ = _map_primitive_data_type(type_name)
        except TypeError:
            logger.warning(
                f"Unknown data type `{type_name}' for attribute `{uml_class.name}.{uml_attr.name}'; using `string'."
            )
            range_ = "string"

    return linkml_model.Slot(
        name=uml_attr.name,
        range=range_,
        description=uml_attr.notes,
        required=_is_slot_required(uml_attr.lower_bound),
        multivalued=_is_slot_multivalued(uml_attr.upper_bound),
        slot_uri=_generate_curie(f"{uml_class.name}.{uml_attr.name}", linkml_model.CIM_PREFIX),
    )


def generate_slot_from_relation(
    uml_relation: uml_model.Relation, uml_project: uml_model.Project, direction
) -> linkml_model.Slot:
    source_class = uml_project.classes.by_id[uml_relation.source_class]
    dest_class = uml_project.classes.by_id[uml_relation.dest_class]

    match direction:
        case "source->dest":
            return linkml_model.Slot(
                name=uml_relation.dest_role or dest_class.name,
                range=dest_class.name,
                description=uml_relation.dest_role_note,
                required=_is_slot_required(uml_relation.dest_card.lower_bound),
                multivalued=_is_slot_multivalued(uml_relation.dest_card.upper_bound),
                slot_uri=_generate_curie(
                    f"{source_class.name}.{uml_relation.dest_role or dest_class.name}",
                    linkml_model.CIM_PREFIX,
                ),
            )
        case "dest->source":
            return linkml_model.Slot(
                name=uml_relation.source_role or source_class.name,
                range=source_class.name,
                description=uml_relation.source_role_note,
                required=_is_slot_required(uml_relation.source_card.lower_bound),
                multivalued=_is_slot_multivalued(uml_relation.source_card.upper_bound),
                slot_uri=_generate_curie(
                    f"{dest_class.name}.{uml_relation.source_role or source_class.name}",
                    linkml_model.CIM_PREFIX,
                ),
            )
        case _:
            raise TypeError(f"Provided direction value was invalid. (relation ID: {uml_relation.id})")


def _generate_schema_id(uml_package: uml_model.Package, uml_project: uml_model.Project) -> linkml_model.URI:
    """
    Example:
    TC57CIM.IEC61970.Dynamics.StandardModels
        ->
    https://cim.ucaiug.io/ns#TC57CIM.IEC61970.Dynamics.StandardModels
    """

    qname = uml_project.packages.get_qualified_name(uml_package.id)
    return linkml_model.CIM_BASE_URI + qname


def _map_primitive_data_type(val):
    if not val:
        return "string"
    mapping = {
        "float": "float",
        "integer": "integer",
        "int": "integer",
        "datetime": "datetime",
        "string": "string",
        "str": "string",
        "boolean": "boolean",
        "bool": "boolean",
        "decimal": "decimal",
        "double": "double",
        "monthday": "string",  # xsd:gMonthDay (--MM-DD) has no LinkML equivalent.
        "date": "date",
        "time": "time",
        "duration": "string",  # xsd:duration, e.g. `P1DT2H'.
        "iri": "uri",
        "uri": "uri",
        "uuid": "string",
    }
    mapped = mapping.get(str(val).lower())
    if mapped:
        return mapped
    raise TypeError(f"Data type `{val}` is not a CIM Primitive.")


def _generate_curie(name: str, prefix: str) -> str:
    return f"{prefix}:{quote(name)}"


@lru_cache(maxsize=1947)
def _get_super_class(uml_class: uml_model.Class, uml_project: uml_model.Project) -> Optional[uml_model.Class]:
    rels = uml_project.relations.by_source_class.get(uml_class.id, [])
    for uml_relation in rels:
        if uml_relation.type != uml_model.RelationType.GENERALIZATION:
            continue

        try:
            source_class = uml_project.classes.by_id[uml_relation.source_class]
        except KeyError as e:
            continue  # Bad data, but no superclass for sure.

        if source_class.id == uml_class.id:
            super_class = uml_project.classes.by_id[uml_relation.dest_class]
            return super_class
    return None


@lru_cache(maxsize=1942)
def _get_attribute_types(uml_class: uml_model.Class, uml_project: uml_model.Project) -> tuple[uml_model.Class, ...]:
    type_classes = tuple(
        class_
        for attr in uml_class.attributes
        if attr.type is not None
        if (class_ := uml_project.classes.by_name.get(attr.type))
    )

    return type_classes


@lru_cache(maxsize=1942)
def _get_related_classes(uml_class: uml_model.Class, uml_project: uml_model.Project) -> tuple[uml_model.Class, ...]:
    from_classes = tuple(
        uml_project.classes.by_id[rel.source_class]
        for rel in uml_project.relations.by_dest_class.get(uml_class.id, [])
        if rel.type != uml_model.RelationType.GENERALIZATION
        if rel.source_class != uml_class.id
    )
    to_classes = tuple(
        uml_project.classes.by_id[rel.dest_class]
        for rel in uml_project.relations.by_source_class.get(uml_class.id, [])
        if rel.type != uml_model.RelationType.GENERALIZATION
    )

    return from_classes + to_classes


def _is_slot_required(lower_bound: uml_model.CardinalityValue) -> bool:
    return lower_bound == "*" or lower_bound > 0


def _is_slot_multivalued(upper_bound: uml_model.CardinalityValue) -> bool:
    return upper_bound == "*" or upper_bound > 1

@lru_cache(maxsize=1942)
def _get_package_version(package_id, uml_project, visited=None) -> Optional[str]:
    if visited is None:
        visited = frozenset()
    if package_id in visited:
        return None
    visited = visited.union({package_id})
    for c in uml_project.classes.by_package.get(package_id, []):
        if c.name and 'CIMVersion' in c.name:
            for attr in c.attributes:
                if attr.name == 'version' and attr.default:
                    return attr.default
    pkg = uml_project.packages.by_id.get(package_id)
    if pkg and pkg.parent and pkg.parent not in (0, None, "", str(pkg.id)):
        return _get_package_version(pkg.parent, uml_project, visited)
    return None

@lru_cache(maxsize=1942)
def _get_package_specification(package_id, uml_project) -> Optional[str]:
    qname = uml_project.packages.get_qualified_name(package_id)
    if "IEC61970" in qname:
        return "IEC 61970-301"
    elif "IEC61968" in qname:
        return "IEC 61968-11"
    elif "IEC62325" in qname:
        return "IEC 62325-301"
    return None


