import logging
from datetime import datetime
from typing import Any, Iterable

from lxml import etree  # type: ignore

import cim_to_linkml.uml_model as uml_model

logger = logging.getLogger(__name__)

def read_xmi_project(file_path: str) -> tuple[list[dict], list[dict], list[dict]]:
    tree = etree.parse(file_path)
    root = tree.getroot()

    # Detect XMI version
    version = root.attrib.get("xmi.version", None)
    if not version:
        version = root.attrib.get("{http://schema.omg.org/spec/XMI/2.1}version", None)
    
    if version == "1.1":
        parser = XMI11Parser(root)
    elif version == "2.1":
        parser = XMI21Parser(root)
    else:
        # Fallback to 1.1 if not specified
        parser = XMI11Parser(root)

    return parser.parse_packages(), parser.parse_classes(), parser.parse_relations()

class XMI11Parser:
    def __init__(self, root: etree._Element):
        self.root = root
        self.ns = {"UML": "omg.org/UML1.3"}

    def _get_tagged_value(self, element: etree._Element, tag: str) -> str | None:
        # Only the element's own tagged values; a descendant search would pick up those of nested elements.
        for tv in element.xpath(
            f'./UML:ModelElement.taggedValue/UML:TaggedValue[@tag="{tag}"]', namespaces=self.ns
        ):
            return tv.attrib.get("value")
        return None

    def parse_packages(self) -> list[dict]:
        packages = []
        for pkg_elem in self.root.xpath('//UML:Package', namespaces=self.ns):
            pkg_id = pkg_elem.attrib.get("xmi.id")
            name = pkg_elem.attrib.get("name")
            parent_id = self._get_tagged_value(pkg_elem, "parent") or pkg_elem.attrib.get("namespace")
            created = self._get_tagged_value(pkg_elem, "date_created") or datetime.now().isoformat()
            modified = self._get_tagged_value(pkg_elem, "date_modified") or datetime.now().isoformat()
            author = self._get_tagged_value(pkg_elem, "author")
            note = self._get_tagged_value(pkg_elem, "documentation")
            
            packages.append({
                "id": pkg_id, "name": name, "parent_id": parent_id,
                "created_date": created, "modified_date": modified,
                "author": author, "note": note,
            })
        return packages

    def parse_classes(self) -> list[dict]:
        # First pass to collect element names for ID resolution
        element_names = {}
        for elem in self.root.xpath('//*[@xmi.id]', namespaces=self.ns):
            element_names[elem.attrib.get("xmi.id")] = elem.attrib.get("name")
            
        classes = []
        for cls_elem in self.root.xpath('//UML:Class', namespaces=self.ns):
            cls_id = cls_elem.attrib.get("xmi.id")
            cls_name = cls_elem.attrib.get("name")
            pkg_id = self._get_tagged_value(cls_elem, "package") or cls_elem.attrib.get("namespace")
            created = self._get_tagged_value(cls_elem, "date_created") or datetime.now().isoformat()
            modified = self._get_tagged_value(cls_elem, "date_modified") or datetime.now().isoformat()
            author = self._get_tagged_value(cls_elem, "author")
            note = self._get_tagged_value(cls_elem, "documentation")
            
            stereotype = self._get_tagged_value(cls_elem, "stereotype")
            if not stereotype:
                st_elem = cls_elem.xpath('./UML:ModelElement.stereotype/UML:Stereotype', namespaces=self.ns)
                if st_elem:
                    stereotype = st_elem[0].attrib.get("name")
                    
            attrs = cls_elem.xpath('.//UML:Attribute', namespaces=self.ns)
            if not attrs:
                classes.append({
                    "class_id": cls_id, "class_name": cls_name, "class_author": author,
                    "class_package_id": pkg_id, "class_created_date": created,
                    "class_modified_date": modified, "class_stereotype": stereotype,
                    "class_note": note,
                    "attr_id": None, "attr_name": None, "attr_lower_bound": None,
                    "attr_upper_bound": None, "attr_type": None, "attr_notes": None,
                    "attr_stereotype": None, "attr_default": None
                })
            else:
                for attr in attrs:
                    attr_id = self._get_tagged_value(attr, "ea_guid") or attr.attrib.get("xmi.id") or id(attr)
                    attr_name = attr.attrib.get("name")
                    
                    lb_tv = self._get_tagged_value(attr, "lowerBound")
                    ub_tv = self._get_tagged_value(attr, "upperBound")
                    if lb_tv is None and ub_tv is None:
                        multiplicity_elem = attr.xpath('.//UML:MultiplicityRange', namespaces=self.ns)
                        if multiplicity_elem:
                            lb_tv = multiplicity_elem[0].attrib.get("lower")
                            ub_tv = multiplicity_elem[0].attrib.get("upper")
                    
                    attr_note = self._get_tagged_value(attr, "description")
                    attr_st = self._get_tagged_value(attr, "stereotype")
                    
                    attr_type_elem = attr.xpath('.//UML:Classifier', namespaces=self.ns)
                    attr_type_id = attr_type_elem[0].attrib.get("xmi.idref") if attr_type_elem else self._get_tagged_value(attr, "type")
                    attr_type = element_names.get(attr_type_id, attr_type_id)

                    initial_elem = attr.xpath('./UML:Attribute.initialValue/UML:Expression', namespaces=self.ns)
                    attr_default = initial_elem[0].attrib.get("body") if initial_elem else None
                    
                    classes.append({
                        "class_id": cls_id, "class_name": cls_name, "class_author": author,
                        "class_package_id": pkg_id, "class_created_date": created,
                        "class_modified_date": modified, "class_stereotype": stereotype,
                        "class_note": note,
                        "attr_id": str(attr_id), "attr_name": attr_name, "attr_lower_bound": lb_tv,
                        "attr_upper_bound": ub_tv, "attr_type": attr_type, "attr_notes": attr_note,
                        "attr_stereotype": attr_st, "attr_default": attr_default
                    })
        return classes

    def parse_relations(self) -> list[dict]:
        relations = []
        for rel_elem in self.root.xpath('//UML:Association', namespaces=self.ns):
            rel_id = rel_elem.attrib.get("xmi.id")
            ends = rel_elem.xpath('./UML:Association.connection/UML:AssociationEnd', namespaces=self.ns)
            if len(ends) == 2:
                source, dest = ends[0], ends[1]
                src_id = source.attrib.get("type")
                dst_id = dest.attrib.get("type")
                
                src_role = source.attrib.get("name")
                dst_role = dest.attrib.get("name")
                
                src_mult = source.attrib.get("multiplicity") or ""
                dst_mult = dest.attrib.get("multiplicity") or ""
                
                src_card = src_mult.replace(".", "..") if ".." not in src_mult else src_mult
                dst_card = dst_mult.replace(".", "..") if ".." not in dst_mult else dst_mult
                
                direction = self._get_tagged_value(rel_elem, "direction") or "Source -> Destination"
                rel_type = self._get_tagged_value(rel_elem, "ea_type") or "Association"
                
                relations.append({
                    "id": rel_id, "type": rel_type,
                    "start_object_id": src_id, "end_object_id": dst_id,
                    "direction": direction,
                    "source_card": src_card, "source_role": src_role,
                    "source_role_note": self._get_tagged_value(source, "description"),
                    "dest_card": dst_card, "dest_role": dst_role,
                    "dest_role_note": self._get_tagged_value(dest, "description"),
                })
                
        for gen_elem in self.root.xpath('//UML:Generalization', namespaces=self.ns):
            rel_id = gen_elem.attrib.get("xmi.id")
            # Enterprise Architect writes `subtype'/`supertype'; UML 1.3 proper uses `child'/`parent'.
            child = gen_elem.attrib.get("child") or gen_elem.attrib.get("subtype")
            parent = gen_elem.attrib.get("parent") or gen_elem.attrib.get("supertype")
            
            if not child or not parent:
                child_elem = gen_elem.xpath('./UML:Generalization.child/UML:Class', namespaces=self.ns)
                parent_elem = gen_elem.xpath('./UML:Generalization.parent/UML:Class', namespaces=self.ns)
                if child_elem: child = child_elem[0].attrib.get("xmi.idref")
                if parent_elem: parent = parent_elem[0].attrib.get("xmi.idref")
                
            if child and parent:
                relations.append({
                    "id": rel_id, "type": "Generalization",
                    "start_object_id": child, "end_object_id": parent,
                    "direction": "Source -> Destination",
                    "source_card": None, "source_role": None, "source_role_note": None,
                    "dest_card": None, "dest_role": None, "dest_role_note": None,
                })
        return relations

class XMI21Parser:
    XMI_ID = "{http://schema.omg.org/spec/XMI/2.1}id"
    XMI_IDREF = "{http://schema.omg.org/spec/XMI/2.1}idref"

    def __init__(self, root: etree._Element):
        self.root = root
        self.ns = {"xmi": "http://schema.omg.org/spec/XMI/2.1", "uml": "http://schema.omg.org/spec/UML/2.1.1"}
        # Map EA IDs back to their element for resolving packages, etc
        self.elements_by_id = {elem.attrib.get(self.XMI_ID): elem for elem in self.root.xpath('//*[@xmi:id]', namespaces=self.ns)}
        self.element_names = {k: v.attrib.get("name") for k, v in self.elements_by_id.items()}
        # Enterprise Architect stores stereotypes, documentation, authors, dates and initial values
        # in its own `xmi:Extension' section rather than in the UML model itself.
        self.ext_elements = {
            elem.attrib.get(self.XMI_IDREF): elem
            for elem in self.root.xpath('/xmi:XMI/xmi:Extension/elements/element', namespaces=self.ns)
        }
        self.ext_attributes = {
            elem.attrib.get(self.XMI_IDREF): elem
            for elem in self.root.xpath('/xmi:XMI/xmi:Extension/elements/element/attributes/attribute', namespaces=self.ns)
        }

    @staticmethod
    def _ext_value(ext_elem: etree._Element | None, path: str, attr: str) -> str | None:
        if ext_elem is None:
            return None
        found = ext_elem.find(path)
        value = found.attrib.get(attr) if found is not None else None
        return value or None

    def _element_info(self, elem_id: str | None) -> dict:
        ext = self.ext_elements.get(elem_id)
        return {
            "note": self._ext_value(ext, "properties", "documentation"),
            "stereotype": self._ext_value(ext, "properties", "stereotype"),
            "author": self._ext_value(ext, "project", "author"),
            "created_date": self._ext_value(ext, "project", "created") or datetime.now().isoformat(),
            "modified_date": self._ext_value(ext, "project", "modified") or datetime.now().isoformat(),
        }

    def parse_packages(self) -> list[dict]:
        packages = []
        for pkg_elem in self.root.xpath('//packagedElement[@xmi:type="uml:Package"]', namespaces=self.ns):
            pkg_id = pkg_elem.attrib.get(self.XMI_ID)
            name = pkg_elem.attrib.get("name")
            parent = pkg_elem.getparent()
            parent_id = parent.attrib.get(self.XMI_ID) if parent is not None else None
            info = self._element_info(pkg_id)

            packages.append({
                "id": pkg_id, "name": name, "parent_id": parent_id,
                "created_date": info["created_date"], "modified_date": info["modified_date"],
                "author": info["author"], "note": info["note"],
            })
        return packages

    def parse_classes(self) -> list[dict]:
        classes = []
        classifier_types = '@xmi:type="uml:Class" or @xmi:type="uml:DataType" or @xmi:type="uml:Enumeration" or @xmi:type="uml:PrimitiveType"'
        for cls_elem in self.root.xpath(
            f'//packagedElement[{classifier_types}] | //nestedClassifier[{classifier_types}]', namespaces=self.ns
        ):
            cls_id = cls_elem.attrib.get(self.XMI_ID)
            cls_name = cls_elem.attrib.get("name")
            if not cls_name:
                continue
            # EA exports diagram notes, text and boundaries as `uml:Class' too; its extension data has the real type.
            ext = self.ext_elements.get(cls_id)
            if ext is not None and ext.attrib.get("{http://schema.omg.org/spec/XMI/2.1}type") not in (
                "uml:Class", "uml:DataType", "uml:Enumeration", "uml:PrimitiveType"
            ):
                continue
            # Nested classifiers belong to the package of their owning class.
            pkg_elem = next(
                (a for a in cls_elem.iterancestors()
                 if a.attrib.get("{http://schema.omg.org/spec/XMI/2.1}type") == "uml:Package"),
                None,
            )
            pkg_id = pkg_elem.attrib.get(self.XMI_ID) if pkg_elem is not None else None
            info = self._element_info(cls_id)
            class_row = {
                "class_id": cls_id, "class_name": cls_name, "class_author": info["author"],
                "class_package_id": pkg_id, "class_created_date": info["created_date"],
                "class_modified_date": info["modified_date"], "class_stereotype": info["stereotype"],
                "class_note": info["note"],
            }

            attrs = cls_elem.xpath(
                './ownedAttribute[@xmi:type="uml:Property"] | ./ownedLiteral', namespaces=self.ns
            )
            if not attrs:
                classes.append({
                    **class_row,
                    "attr_id": None, "attr_name": None, "attr_lower_bound": None,
                    "attr_upper_bound": None, "attr_type": None, "attr_notes": None,
                    "attr_stereotype": None, "attr_default": None
                })
            else:
                for attr in attrs:
                    attr_id = attr.attrib.get(self.XMI_ID)
                    attr_name = attr.attrib.get("name")
                    
                    lb_elem = attr.xpath('./lowerValue', namespaces=self.ns)
                    ub_elem = attr.xpath('./upperValue', namespaces=self.ns)
                    lb = lb_elem[0].attrib.get("value") if lb_elem else None
                    ub = ub_elem[0].attrib.get("value") if ub_elem else None
                    
                    type_elem = attr.xpath('./type', namespaces=self.ns)
                    attr_type_id = type_elem[0].attrib.get(self.XMI_IDREF) if type_elem else None
                    attr_type = self.element_names.get(attr_type_id, attr_type_id)

                    attr_ext = self.ext_attributes.get(attr_id)
                    
                    classes.append({
                        **class_row,
                        "attr_id": attr_id, "attr_name": attr_name, "attr_lower_bound": lb,
                        "attr_upper_bound": ub, "attr_type": attr_type,
                        "attr_notes": self._ext_value(attr_ext, "documentation", "value"),
                        "attr_stereotype": self._ext_value(attr_ext, "stereotype", "stereotype"),
                        "attr_default": self._ext_value(attr_ext, "initial", "body"),
                    })
        return classes

    def parse_relations(self) -> list[dict]:
        relations = []
        for rel_elem in self.root.xpath('//packagedElement[@xmi:type="uml:Association"]', namespaces=self.ns):
            rel_id = rel_elem.attrib.get("{http://schema.omg.org/spec/XMI/2.1}id")
            ends = rel_elem.xpath('./ownedEnd', namespaces=self.ns)
            if len(ends) == 2:
                source, dest = ends[0], ends[1]
                src_type = source.xpath('./type', namespaces=self.ns)
                dst_type = dest.xpath('./type', namespaces=self.ns)
                src_id = src_type[0].attrib.get("{http://schema.omg.org/spec/XMI/2.1}idref") if src_type else None
                dst_id = dst_type[0].attrib.get("{http://schema.omg.org/spec/XMI/2.1}idref") if dst_type else None
                
                src_lb = source.xpath('./lowerValue', namespaces=self.ns)
                src_ub = source.xpath('./upperValue', namespaces=self.ns)
                dst_lb = dest.xpath('./lowerValue', namespaces=self.ns)
                dst_ub = dest.xpath('./upperValue', namespaces=self.ns)
                
                s_l = src_lb[0].attrib.get("value", "0") if src_lb else "0"
                s_u = src_ub[0].attrib.get("value", "1") if src_ub else "1"
                d_l = dst_lb[0].attrib.get("value", "0") if dst_lb else "0"
                d_u = dst_ub[0].attrib.get("value", "1") if dst_ub else "1"
                
                relations.append({
                    "id": rel_id, "type": "Association",
                    "start_object_id": src_id, "end_object_id": dst_id,
                    "direction": "Source -> Destination",
                    "source_card": f"{s_l}..{s_u}", "source_role": source.attrib.get("name"),
                    "source_role_note": None,
                    "dest_card": f"{d_l}..{d_u}", "dest_role": dest.attrib.get("name"),
                    "dest_role_note": None,
                })
                
        for gen_elem in self.root.xpath('//generalization', namespaces=self.ns):
            rel_id = gen_elem.attrib.get("{http://schema.omg.org/spec/XMI/2.1}id")
            parent = gen_elem.attrib.get("general")
            child = gen_elem.getparent().attrib.get("{http://schema.omg.org/spec/XMI/2.1}id")
            
            if child and parent:
                relations.append({
                    "id": rel_id, "type": "Generalization",
                    "start_object_id": child, "end_object_id": parent,
                    "direction": "Source -> Destination",
                    "source_card": None, "source_role": None, "source_role_note": None,
                    "dest_card": None, "dest_role": None, "dest_role_note": None,
                })
        return relations
