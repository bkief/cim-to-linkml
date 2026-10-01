from datetime import datetime
from typing import Any, Optional

import rdflib
from rdflib.namespace import OWL, RDF, RDFS

from . import uml_model

CIMS_NS = rdflib.Namespace("http://iec.ch/TC57/1999/rdf-schema-extensions-19990926#")
UML_NS = rdflib.Namespace("http://langdale.com.au/2005/UML#")

def parse_iso_datetime_val(val: Optional[str]) -> datetime:
    if val is None:
        return datetime.now()
    return datetime.fromisoformat(val)

def _get_local_name(uri: str) -> str:
    if "#" in uri:
        return uri.split("#")[-1]
    return uri.split("/")[-1]

def read_rdf_project(filepath: str) -> uml_model.Project:
    graph = rdflib.Graph()
    # Try parsing, rdflib will guess format or we can provide format=rdflib.util.guess_format(filepath)
    try:
        format_guess = rdflib.util.guess_format(filepath)
        if format_guess is None:
            if filepath.endswith('.ttl'):
                format_guess = 'turtle'
            elif filepath.endswith('.rdf') or filepath.endswith('.xml') or filepath.endswith('.owl') or filepath.endswith('.rdfs'):
                format_guess = 'xml'
            else:
                format_guess = 'xml'
        graph.parse(filepath, format=format_guess)
    except Exception as e:
        print(f"Failed to parse RDF file {filepath}: {e}")
        raise e

    packages = set()
    classes = set()
    relations = set()

    # Discover all packages from ClassCategory and belongsToCategory
    category_nodes = set(graph.subjects(RDF.type, CIMS_NS.ClassCategory)).union(
        set(graph.objects(None, CIMS_NS.belongsToCategory))
    )

    def resolve_package_name(cat_node) -> str:
        if cat_node is None:
            return "Model"
        cat_label = graph.value(cat_node, RDFS.label)
        if cat_label:
            return str(cat_label).strip()
        raw = _get_local_name(str(cat_node))
        return raw.removeprefix("Package_") if raw.startswith("Package_") else raw

    packages_by_name = {}

    def get_or_create_package(package_name: str, notes: str = "") -> str:
        if not package_name:
            package_name = "GlobalPackage"
        if package_name not in packages_by_name:
            pkg_id = f"PKG_{package_name}"
            packages_by_name[package_name] = pkg_id
            packages.add(uml_model.Package(
                id=pkg_id,
                name=package_name,
                author="",
                created_date=datetime.now(),
                modified_date=datetime.now(),
                notes=notes,
                parent=None
            ))
        return packages_by_name[package_name]

    # Pre-populate discovered packages
    for cat_node in category_nodes:
        p_name = resolve_package_name(cat_node)
        comment = graph.value(cat_node, RDFS.comment)
        notes = str(comment) if comment else ""
        get_or_create_package(p_name, notes=notes)

    # Track nodes to build up our models
    raw_class_nodes = set(graph.subjects(RDF.type, OWL.Class)).union(set(graph.subjects(RDF.type, RDFS.Class)))
    # Exclude blank nodes, owl:Thing, and category nodes
    class_nodes = {
        n for n in raw_class_nodes
        if isinstance(n, rdflib.URIRef) and n != OWL.Thing and n not in category_nodes
    }

    raw_property_nodes = set(graph.subjects(RDF.type, OWL.ObjectProperty)).union(
        set(graph.subjects(RDF.type, OWL.DatatypeProperty))
    ).union(
        set(graph.subjects(RDF.type, RDF.Property))
    )
    property_nodes = {p for p in raw_property_nodes if isinstance(p, rdflib.URIRef)}

    class_attributes = {str(c): [] for c in class_nodes}
    enum_literals_by_class = {}

    for cls_node in class_nodes:
        cls_uri = str(cls_node)

        # Determine stereotype
        stereotype = None
        st_val = graph.value(cls_node, CIMS_NS.stereotype) or graph.value(cls_node, UML_NS.hasStereotype)
        if st_val:
            st_str = str(st_val).lower()
            if "enum" in st_str or st_str.endswith("enumeration"):
                stereotype = uml_model.ClassStereotype.ENUMERATION
            elif "primitive" in st_str:
                stereotype = uml_model.ClassStereotype.PRIMITIVE
            elif "datatype" in st_str:
                stereotype = uml_model.ClassStereotype.CIMDATATYPE
            elif "compound" in st_str:
                stereotype = uml_model.ClassStereotype.COMPOUND

        # Enums may not use attributes but instead use individuals of this class type
        if stereotype == uml_model.ClassStereotype.ENUMERATION:
            literals = list(graph.subjects(RDF.type, cls_node))
            attributes = []
            for lit in literals:
                lit_name = _get_local_name(str(lit))
                lit_label = graph.value(lit, RDFS.label)
                if lit_label:
                    lit_name = str(lit_label).strip()
                elif "." in lit_name:
                    lit_name = lit_name.split(".")[-1]
                lit_notes = graph.value(lit, RDFS.comment)
                attributes.append(uml_model.Attribute(
                    id=str(lit),
                    class_=cls_uri,
                    name=lit_name,
                    type=None,
                    lower_bound=0,
                    upper_bound=1,
                    notes=str(lit_notes) if lit_notes else "",
                    default=None,
                    stereotype=None
                ))
            enum_literals_by_class[cls_uri] = attributes

    class_node_uris = {str(c) for c in class_nodes}

    association_ends: dict[str, dict] = {}

    for prop_node in property_nodes:
        prop_uri = str(prop_node)
        
        prop_label = graph.value(prop_node, RDFS.label)
        if prop_label:
            prop_name = str(prop_label).strip()
        else:
            raw_name = _get_local_name(prop_uri)
            prop_name = raw_name.split(".")[-1] if "." in raw_name else raw_name

        domain = graph.value(prop_node, RDFS.domain)
        range_ = graph.value(prop_node, RDFS.range)

        if not domain or str(domain) not in class_node_uris:
            continue

        domain_uri = str(domain)

        # Check stereotype
        is_attribute = False
        is_relation = False
        st_val = graph.value(prop_node, CIMS_NS.stereotype) or graph.value(prop_node, UML_NS.hasStereotype)
        if st_val:
            st_str = str(st_val).lower()
            if "attribute" in st_str:
                is_attribute = True
            elif "association" in st_str:
                is_relation = True

        # If no stereotype, guess based on range
        if not is_attribute and not is_relation:
            if range_ and str(range_) in class_node_uris:
                is_relation = True
            else:
                is_attribute = True

        notes = graph.value(prop_node, RDFS.comment)
        notes_str = str(notes) if notes else ""

        # Multiplicity
        lower: uml_model.CardinalityValue = 0
        upper: uml_model.CardinalityValue = 1
        mult = graph.value(prop_node, CIMS_NS.multiplicity)
        if mult:
            mult_str = _get_local_name(str(mult))
            if ".." in mult_str:
                parts = mult_str.split("..")
                l_str = parts[0].replace("M:", "")
                u_str = parts[1]
                lower = int(l_str) if l_str.isdigit() else 0
                upper = "*" if u_str in ("*", "n") else (int(u_str) if u_str.isdigit() else 1)

        if is_relation and range_ and str(range_) in class_node_uris:
            # Each RDF property is one association end, navigable from its domain to its range.
            inverse = graph.value(prop_node, CIMS_NS.inverseRoleName) or graph.value(prop_node, OWL.inverseOf)
            association_ends[prop_uri] = {
                "name": prop_name,
                "domain": domain_uri,
                "range": str(range_),
                "card": uml_model.Cardinality(lower_bound=lower, upper_bound=upper),
                "notes": notes_str,
                "inverse": str(inverse) if inverse else None,
            }
        elif is_attribute:
            type_name = "String"
            if range_:
                type_name = _get_local_name(str(range_))
                if type_name == "string": type_name = "String"
                elif type_name == "boolean": type_name = "Boolean"
                elif type_name == "integer": type_name = "Integer"
                elif type_name == "float": type_name = "Float"
                elif type_name == "decimal": type_name = "Decimal"
                elif type_name == "date": type_name = "Date"
                elif type_name == "dateTime": type_name = "DateTime"
                elif type_name == "time": type_name = "Time"
            attr = uml_model.Attribute(
                id=prop_uri,
                class_=domain_uri,
                name=prop_name,
                type=type_name,
                lower_bound=lower,
                upper_bound=upper,
                notes=notes_str,
                default=None,
                stereotype=None
            )
            class_attributes[domain_uri].append(attr)

    # Pair association ends with their inverse (if present) into a single relation.
    paired = set()
    for end_uri, end in sorted(association_ends.items()):
        if end_uri in paired:
            continue
        inverse = association_ends.get(end["inverse"]) if end["inverse"] else None
        if inverse and inverse["domain"] == end["range"] and end["inverse"] not in paired:
            paired.update({end_uri, end["inverse"]})
        else:
            inverse = None
        relations.add(uml_model.Relation(
            id=end_uri,
            type=uml_model.RelationType.ASSOCIATION,
            source_class=end["domain"],
            dest_class=end["range"],
            direction=uml_model.RelationDirection.SOURCE_TO_DESTINATION,
            dest_role=end["name"],
            dest_card=end["card"],
            dest_role_note=end["notes"],
            source_role=inverse["name"] if inverse else None,
            source_card=inverse["card"] if inverse else uml_model.Cardinality(),
            source_role_note=inverse["notes"] if inverse else None,
            bidirectional=inverse is not None,
        ))

    # Construct final class models
    for cls_node in class_nodes:
        cls_uri = str(cls_node)
        cls_name = _get_local_name(cls_uri)
        if not cls_name:
            lbl = graph.value(cls_node, RDFS.label)
            cls_name = str(lbl).strip() if lbl else cls_uri

        stereotype = None
        st_val = graph.value(cls_node, CIMS_NS.stereotype) or graph.value(cls_node, UML_NS.hasStereotype)
        if st_val:
            st_str = str(st_val).lower()
            if "enum" in st_str or st_str.endswith("enumeration"):
                stereotype = uml_model.ClassStereotype.ENUMERATION
            elif "primitive" in st_str:
                stereotype = uml_model.ClassStereotype.PRIMITIVE
            elif "datatype" in st_str:
                stereotype = uml_model.ClassStereotype.CIMDATATYPE
            elif "compound" in st_str:
                stereotype = uml_model.ClassStereotype.COMPOUND

        pkg_name = "Model"
        category = graph.value(cls_node, CIMS_NS.belongsToCategory)
        if category:
            pkg_name = resolve_package_name(category)

        pkg_id = get_or_create_package(pkg_name)
        notes = graph.value(cls_node, RDFS.comment)

        attributes = class_attributes.get(cls_uri, [])
        if stereotype == uml_model.ClassStereotype.ENUMERATION:
            attributes.extend(enum_literals_by_class.get(cls_uri, []))

        classes.add(uml_model.Class(
            id=cls_uri,
            name=cls_name,
            author="",
            package=pkg_id,
            attributes=tuple(attributes),
            created_date=datetime.now(),
            modified_date=datetime.now(),
            note=str(notes) if notes else "",
            stereotype=stereotype
        ))

    # If no package was created, ensure at least one default package exists
    if not packages:
        get_or_create_package("Model")

    # Resolve subclasses
    for cls_node in class_nodes:
        for subclass_of in graph.objects(cls_node, RDFS.subClassOf):
            if subclass_of in class_nodes:
                relations.add(uml_model.Relation(
                    id=f"{cls_node}_subclassOf_{subclass_of}",
                    type=uml_model.RelationType.GENERALIZATION,
                    source_class=str(cls_node),
                    dest_class=str(subclass_of),
                    direction=uml_model.RelationDirection.SOURCE_TO_DESTINATION,
                    source_role="",
                    dest_role="",
                    source_card=uml_model.Cardinality(1, 1),
                    dest_card=uml_model.Cardinality(1, 1),
                    source_role_note=""
                ))

    return uml_model.Project(
        packages=uml_model.Packages(packages),
        classes=uml_model.Classes(classes),
        relations=uml_model.Relations(relations)
    )
