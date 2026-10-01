import logging
import os
from datetime import datetime
from enum import Enum
from functools import cached_property, lru_cache
from itertools import groupby
from operator import attrgetter, itemgetter
from typing import Iterable, Literal, NamedTuple, Optional

ObjectID = int | str
ConnectorID = int | str
AttributeID = int | str
AttributeName = str
RelationName = str
ClassName = str
PackageName = str
Many = Literal["*"]
CardinalityValue = int | Many

QEAFile = os.PathLike | str

logger = logging.getLogger(__name__)


class Cardinality(NamedTuple):
    lower_bound: CardinalityValue = 0
    upper_bound: CardinalityValue = 1


class RelationSubType(Enum):
    WEAK = "Weak"


class RelationDirection(Enum):
    SOURCE_TO_DESTINATION = "Source -> Destination"
    UNSPECIFIED = "Unspecified"
    BI_DIRECTIONAL = "Bi-Directional"


class RelationType(Enum):
    AGGREGATION = "Aggregation"
    ASSOCIATION = "Association"
    DEPENDENCY = "Dependency"
    GENERALIZATION = "Generalization"
    NOTELINK = "NoteLink"
    PACKAGE = "Package"


class ClassStereotype(Enum):
    CIMDATATYPE = "CIMDatatype"
    PRIMITIVE = "Primitive"
    ENUMERATION = "enumeration"
    COMPOUND = "Compound"
    IMAGE = "Image"
    DATATYPE = "CIMDatatype"


class AttributeStereotype(Enum):
    ENUM = "enum"
    DEPRECATED = "deprecated"


class Package(NamedTuple):
    id: ObjectID
    name: PackageName
    notes: Optional[str] = None
    author: Optional[str] = None
    created_date: datetime = datetime.now()
    modified_date: datetime = datetime.now()
    parent: Optional[ObjectID] = None


class Attribute(NamedTuple):
    id: AttributeID
    class_: ObjectID
    name: AttributeName
    lower_bound: CardinalityValue = 0
    upper_bound: CardinalityValue = 1
    type: Optional[ClassName] = None  # `NULL` for enumeration values, a class name otherwise.
    default: Optional[str] = None
    notes: Optional[str] = None
    stereotype: Optional[AttributeStereotype] = None


class Class(NamedTuple):
    id: ObjectID
    name: ClassName
    package: ObjectID
    attributes: tuple[Attribute, ...]
    created_date: datetime = datetime.now()
    modified_date: datetime = datetime.now()
    author: Optional[str] = None
    note: Optional[str] = None
    stereotype: Optional[ClassStereotype] = None


class Relation(NamedTuple):
    id: ConnectorID
    type: RelationType
    source_class: ObjectID
    dest_class: ObjectID
    direction: Optional[RelationDirection] = None
    # sub_type: Optional[RelationSubType] = None
    source_card: Cardinality = Cardinality()
    source_role: Optional[str] = None
    source_role_note: Optional[str] = None
    dest_card: Cardinality = Cardinality()
    dest_role: Optional[str] = None
    dest_role_note: Optional[str] = None
    # False when only the source -> destination end is known (e.g. an RDF property without an inverse),
    # in which case no slot is generated on the destination class.
    bidirectional: bool = True


class Classes:
    def __init__(self, classes: Iterable[Class]):
        self._data = classes

    @cached_property
    def by_id(self):
        return {c.id: c for c in sorted(self._data, key=lambda x: str(x.id) if x.id is not None else "")}

    @cached_property
    def by_name(self):
        key = lambda x: str(x.name) if x.name is not None else ""

        classes_by_name = {}
        for name, classes in groupby(sorted(self._data, key=key), key=key):
            classes = list(sorted(classes, key=lambda x: str(x.id) if x.id is not None else ""))
            class_ = classes[0]
            if len(classes) > 1:
                logger.warning(
                    f"Multiple classes with name {name}. Choosing one (object ID: {class_.id}) "
                    f"and skipping the others (object IDs: {', '.join(str(c.id) for c in classes[1:])})."
                )
            classes_by_name[name] = class_

        return classes_by_name

    @cached_property
    def by_package(self):
        key = lambda x: str(x.package) if x.package is not None else ""

        classes_by_package = {}
        for _, group in groupby(sorted(self._data, key=key), key=key):
            cls_list = list(sorted(group, key=lambda x: str(x.id) if x.id is not None else ""))
            classes_by_package[cls_list[0].package] = cls_list

        return classes_by_package


class Relations:
    def __init__(self, relations: Iterable[Relation]):
        self._data = relations

    @cached_property
    def by_id(self):
        return {r.id: r for r in sorted(self._data, key=lambda x: str(x.id) if x.id is not None else "")}

    @cached_property
    def by_source_class(self):
        key = lambda x: str(x.source_class) if x.source_class is not None else ""

        relations_by_source_class = {}
        for _, group in groupby(sorted(self._data, key=key), key=key):
            rel_list = list(sorted(group, key=lambda x: str(x.id) if x.id is not None else ""))
            relations_by_source_class[rel_list[0].source_class] = rel_list

        return relations_by_source_class

    @cached_property
    def by_dest_class(self):
        key = lambda x: str(x.dest_class) if x.dest_class is not None else ""

        relations_by_dest_class = {}
        for _, group in groupby(sorted(self._data, key=key), key=key):
            rel_list = list(sorted(group, key=lambda x: str(x.id) if x.id is not None else ""))
            relations_by_dest_class[rel_list[0].dest_class] = rel_list

        return relations_by_dest_class


class Packages:
    def __init__(self, packages: Iterable[Package]):
        self._data = packages

    @cached_property
    def by_id(self):
        return {p.id: p for p in sorted(self._data, key=lambda x: str(x.id) if x.id is not None else "")}

    @cached_property
    def by_qualified_name(self):
        return {self.get_qualified_name(p_id): p for p_id, p in self.by_id.items()}

    @lru_cache(maxsize=None)
    def get_qualified_name(self, package_id):
        return ".".join(self._get_package_path(package_id))

    def is_leaf_package(self, qname: str):
        return len([qn for qn in self.by_qualified_name if is_package_or_subpackage(qn, qname)]) == 1

    def _get_package_path(self, start_pkg_id, package_path=None, visited=None):
        if package_path is None:
            package_path = []
        if visited is None:
            visited = set()

        if start_pkg_id in visited:
            return package_path  # Break cycle
        visited.add(start_pkg_id)

        package = self.by_id.get(start_pkg_id)
        if not package:
            return package_path

        if package.parent in (0, None, "", str(package.id)):
            return [package.name] + package_path

        return self._get_package_path(package.parent, [package.name] + package_path, visited)


def is_package_or_subpackage(qname: str, package_qname: str) -> bool:
    """True if `qname' is `package_qname' itself or nested in it (`Base.Core' is not inside `Base.Co')."""
    return qname == package_qname or qname.startswith(package_qname + ".")


class Project:
    def __init__(self, packages: Packages, classes: Classes, relations: Relations) -> None:
        self.packages = packages
        self.classes = classes
        self.relations = relations
