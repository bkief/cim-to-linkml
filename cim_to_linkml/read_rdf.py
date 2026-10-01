import rdflib
from rdflib.namespace import RDF, RDFS, OWL
from datetime import datetime
from typing import Optional, Any
from . import uml_model

CIMS_NS = rdflib.Namespace("http://iec.ch/TC57/1999/rdf-schema-extensions-19990926#")

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
            elif filepath.endswith('.rdf') or filepath.endswith('.xml') or filepath.endswith('.owl'):
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
    
    # Track nodes to build up our models
    class_nodes = set(graph.subjects(RDF.type, OWL.Class)).union(set(graph.subjects(RDF.type, RDFS.Class)))
    property_nodes = set(graph.subjects(RDF.type, OWL.ObjectProperty)).union(
                     set(graph.subjects(RDF.type, OWL.DatatypeProperty))).union(
                     set(graph.subjects(RDF.type, RDF.Property)))

    packages_by_name = {}

    def get_or_create_package(package_name: str) -> str:
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
                notes="",
                parent=None
            ))
        return packages_by_name[package_name]

    # Pre-parse enum literals and classes
    enum_literals_by_class = {}
    
    for cls_node in class_nodes:
        cls_uri = str(cls_node)
        cls_name = _get_local_name(cls_uri)
        
        # Determine stereotype
        stereotype = None
        st_val = graph.value(cls_node, CIMS_NS.stereotype)
        if st_val:
            st_str = str(st_val).lower()
            if "enum" in st_str or st_str.endswith("enumeration"):
                stereotype = uml_model.ClassStereotype.ENUMERATION
            elif "primitive" in st_str:
                stereotype = uml_model.ClassStereotype.PRIMITIVE
            elif "datatype" in st_str:
                stereotype = uml_model.ClassStereotype.DATATYPE

        # Determine package
        # Sometimes classes have cims:belongsToCategory
        pkg_name = "Model"
        category = graph.value(cls_node, CIMS_NS.belongsToCategory)
        if category:
            pkg_name = _get_local_name(str(category))
            
        pkg_id = get_or_create_package(pkg_name)
        
        # Get notes
        notes = graph.value(cls_node, RDFS.comment)
        notes_str = str(notes) if notes else ""

        # Enums may not use attributes but instead use individuals of this class type
        if stereotype == uml_model.ClassStereotype.ENUMERATION:
            literals = list(graph.subjects(RDF.type, cls_node))
            attributes = []
            for lit in literals:
                lit_name = _get_local_name(str(lit))
                lit_notes = graph.value(lit, RDFS.comment)
                attributes.append(uml_model.Attribute(
                    id=str(lit),
                    class_=cls_uri,
                    name=lit_name,
                    type="String",
                    lower_bound=0,
                    upper_bound=1,
                    notes=str(lit_notes) if lit_notes else "",
                    default=None,
                    stereotype=None
                ))
            enum_literals_by_class[cls_uri] = attributes

    # Now parse classes and properties
    class_attributes = {str(c): [] for c in class_nodes}

    for prop_node in property_nodes:
        prop_uri = str(prop_node)
        prop_name = _get_local_name(prop_uri)
        
        domain = graph.value(prop_node, RDFS.domain)
        range_ = graph.value(prop_node, RDFS.range)
        
        if not domain:
            continue
            
        domain_uri = str(domain)
        
        # Check stereotype
        is_attribute = False
        is_relation = False
        st_val = graph.value(prop_node, CIMS_NS.stereotype)
        if st_val:
            st_str = str(st_val).lower()
            if "attribute" in st_str:
                is_attribute = True
            elif "association" in st_str:
                is_relation = True
                
        # If no stereotype, guess based on range
        if not is_attribute and not is_relation:
            if range_:
                range_str = str(range_)
                if range_str in class_attributes:
                    is_relation = True
                else:
                    is_attribute = True
            else:
                is_attribute = True

        notes = graph.value(prop_node, RDFS.comment)
        notes_str = str(notes) if notes else ""

        # Multiplicity
        lower = 0
        upper = 1
        mult = graph.value(prop_node, CIMS_NS.multiplicity)
        if mult:
            mult_str = _get_local_name(str(mult))
            if ".." in mult_str:
                parts = mult_str.split("..")
                l_str = parts[0].replace("M:", "")
                u_str = parts[1]
                lower = int(l_str) if l_str.isdigit() else l_str
                upper = "*" if u_str == "n" else (int(u_str) if u_str.isdigit() else u_str)

        if is_attribute:
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
            if domain_uri in class_attributes:
                class_attributes[domain_uri].append(attr)
                
        elif is_relation:
            if range_:
                relations.add(uml_model.Relation(
                    id=prop_uri,
                    type=uml_model.RelationType.ASSOCIATION,
                    source_class=domain_uri,
                    dest_class=str(range_),
                    direction=uml_model.RelationDirection.SOURCE_TO_DESTINATION,
                    source_role=prop_name,
                    dest_role=prop_name, # Often RDF/OWL doesn't explicitly store reciprocal role names on the same property easily without inverseOf
                    source_card=uml_model.Cardinality(lower_bound=lower, upper_bound=upper),
                    dest_card=uml_model.Cardinality(lower_bound=0, upper_bound="*"),
                    source_role_note=notes_str
                ))

    # Construct final class models
    for cls_node in class_nodes:
        cls_uri = str(cls_node)
        cls_name = _get_local_name(cls_uri)
        
        stereotype = None
        st_val = graph.value(cls_node, CIMS_NS.stereotype)
        if st_val:
            st_str = str(st_val).lower()
            if "enum" in st_str or st_str.endswith("enumeration"):
                stereotype = uml_model.ClassStereotype.ENUMERATION
            elif "primitive" in st_str:
                stereotype = uml_model.ClassStereotype.PRIMITIVE
            elif "datatype" in st_str:
                stereotype = uml_model.ClassStereotype.DATATYPE
                
        pkg_name = "Model"
        category = graph.value(cls_node, CIMS_NS.belongsToCategory)
        if category:
            pkg_name = _get_local_name(str(category))
            
        pkg_id = get_or_create_package(pkg_name)
        notes = graph.value(cls_node, RDFS.comment)
        
        attributes = class_attributes.get(cls_uri, [])
        if stereotype == uml_model.ClassStereotype.ENUMERATION:
            attributes.extend(enum_literals_by_class.get(cls_uri, []))
            
        # (Already has class_ from creation above)

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
