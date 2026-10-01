from datetime import datetime
import pytest

from cim_to_linkml.parser import (
    parse_cardinality,
    parse_cardinality_val,
    parse_iso_datetime_val,
    parse_uml_package,
    parse_uml_relation,
    parse_uml_class,
    parse_uml_project,
    _parse_uml_class_attr,
)
import cim_to_linkml.uml_model as uml_model


class TestCardinalityParsing:
    def test_parse_cardinality_val_empty_and_none(self):
        assert parse_cardinality_val("") == 0
        assert parse_cardinality_val(None) == 0

    def test_parse_cardinality_val_wildcards(self):
        assert parse_cardinality_val("*") == "*"
        assert parse_cardinality_val("n") == "*"

    def test_parse_cardinality_val_integers(self):
        assert parse_cardinality_val("0") == 0
        assert parse_cardinality_val("1") == 1
        assert parse_cardinality_val("5") == 5

    def test_parse_cardinality_none(self):
        card = parse_cardinality(None)
        assert card.lower_bound == 0
        assert card.upper_bound == 1

    def test_parse_cardinality_range_zero_to_one(self):
        card = parse_cardinality("0..1")
        assert card.lower_bound == 0
        assert card.upper_bound == 1

    def test_parse_cardinality_range_zero_to_many(self):
        card = parse_cardinality("0..*")
        assert card.lower_bound == 0
        assert card.upper_bound == "*"

    def test_parse_cardinality_range_zero_to_n(self):
        card = parse_cardinality("0..n")
        assert card.lower_bound == 0
        assert card.upper_bound == "*"

    def test_parse_cardinality_range_one_to_one(self):
        card = parse_cardinality("1..1")
        assert card.lower_bound == 1
        assert card.upper_bound == 1

    def test_parse_cardinality_range_one_to_many(self):
        card = parse_cardinality("1..*")
        assert card.lower_bound == 1
        assert card.upper_bound == "*"

    def test_parse_cardinality_single_val(self):
        # UML "1" means exactly one.
        card = parse_cardinality("1")
        assert card.lower_bound == 1
        assert card.upper_bound == 1

    def test_parse_cardinality_single_wildcard(self):
        card = parse_cardinality("*")
        assert card.lower_bound == 0
        assert card.upper_bound == "*"


class TestDateTimeParsing:
    def test_parse_iso_datetime_val_none(self):
        dt = parse_iso_datetime_val(None)
        assert isinstance(dt, datetime)

    def test_parse_iso_datetime_val_valid_iso(self):
        dt = parse_iso_datetime_val("2026-01-15T10:30:00")
        assert dt == datetime(2026, 1, 15, 10, 30, 0)

    def test_parse_iso_datetime_val_date_only(self):
        dt = parse_iso_datetime_val("2026-01-15")
        assert dt.year == 2026
        assert dt.month == 1
        assert dt.day == 15


class TestModelParsing:
    def test_parse_uml_package(self):
        pkg_row = {
            "id": 101,
            "name": "Core",
            "author": "CIM WG",
            "parent_id": 1,
            "created_date": "2026-01-01T00:00:00",
            "modified_date": "2026-01-02T00:00:00",
            "note": "Core package note",
        }
        pkg = parse_uml_package(pkg_row)
        assert pkg.id == 101
        assert pkg.name == "Core"
        assert pkg.author == "CIM WG"
        assert pkg.parent == 1
        assert pkg.notes == "Core package note"
        assert isinstance(pkg.created_date, datetime)

    def test_parse_uml_relation(self):
        rel_row = {
            "id": 201,
            "type": "Association",
            "start_object_id": 10,
            "end_object_id": 20,
            "direction": "Source -> Destination",
            "source_card": "0..1",
            "source_role": "Parent",
            "source_role_note": "Parent note",
            "dest_card": "0..*",
            "dest_role": "Children",
            "dest_role_note": "Children note",
        }
        rel = parse_uml_relation(rel_row)
        assert rel is not None
        assert rel.id == 201
        assert rel.type == uml_model.RelationType.ASSOCIATION
        assert rel.source_class == 10
        assert rel.dest_class == 20
        assert rel.direction == uml_model.RelationDirection.SOURCE_TO_DESTINATION
        assert rel.source_card.lower_bound == 0
        assert rel.source_card.upper_bound == 1
        assert rel.dest_card.lower_bound == 0
        assert rel.dest_card.upper_bound == "*"
        assert rel.source_role == "Parent"
        assert rel.dest_role == "Children"

    def test_parse_uml_relation_unknown_direction(self):
        rel_row = {
            "id": 202,
            "type": "Generalization",
            "start_object_id": 10,
            "end_object_id": 20,
            "direction": "InvalidDirection",
            "source_card": None,
            "source_role": None,
            "source_role_note": None,
            "dest_card": None,
            "dest_role": None,
            "dest_role_note": None,
        }
        rel = parse_uml_relation(rel_row)
        assert rel is not None
        assert rel.direction is None
        assert rel.type == uml_model.RelationType.GENERALIZATION

    def test_parse_uml_relation_unsupported_type_is_skipped(self):
        # EA connector types such as `Abstraction' (present in CIM18) must not crash parsing.
        rel_row = {
            "id": 203,
            "type": "Abstraction",
            "start_object_id": 10,
            "end_object_id": 20,
            "direction": "Source -> Destination",
            "source_card": None,
            "source_role": None,
            "source_role_note": None,
            "dest_card": None,
            "dest_role": None,
            "dest_role_note": None,
        }
        assert parse_uml_relation(rel_row) is None

    def test_parse_uml_class_with_attributes(self):
        class_rows = [
            {
                "class_id": 10,
                "class_name": "ACLineSegment",
                "class_author": "TC57",
                "class_package_id": 100,
                "class_created_date": "2026-01-01T00:00:00",
                "class_modified_date": "2026-01-02T00:00:00",
                "class_note": "AC line segment representation.",
                "class_stereotype": None,
                "attr_id": 301,
                "attr_name": "r",
                "attr_lower_bound": "0",
                "attr_upper_bound": "1",
                "attr_type": "Float",
                "attr_default": "0.0",
                "attr_notes": "Positive sequence series resistance.",
                "attr_stereotype": None,
            },
            {
                "class_id": 10,
                "class_name": "ACLineSegment",
                "class_author": "TC57",
                "class_package_id": 100,
                "class_created_date": "2026-01-01T00:00:00",
                "class_modified_date": "2026-01-02T00:00:00",
                "class_note": "AC line segment representation.",
                "class_stereotype": None,
                "attr_id": 302,
                "attr_name": "x",
                "attr_lower_bound": "1",
                "attr_upper_bound": "1",
                "attr_type": "Float",
                "attr_default": None,
                "attr_notes": "Positive sequence series reactance.",
                "attr_stereotype": None,
            },
        ]
        cls = parse_uml_class(class_rows)
        assert cls.id == 10
        assert cls.name == "ACLineSegment"
        assert len(cls.attributes) == 2
        r_attr = next(a for a in cls.attributes if a.name == "r")
        assert r_attr.type == "Float"
        assert r_attr.lower_bound == 0
        assert r_attr.upper_bound == 1
        assert r_attr.default == "0.0"

    def test_parse_uml_class_stereotype(self):
        class_rows = [
            {
                "class_id": 50,
                "class_name": "UnitMultiplier",
                "class_author": "TC57",
                "class_package_id": 100,
                "class_created_date": "2026-01-01T00:00:00",
                "class_modified_date": "2026-01-02T00:00:00",
                "class_note": "Units enumeration.",
                "class_stereotype": "enumeration",
                "attr_id": None,
                "attr_name": None,
                "attr_lower_bound": None,
                "attr_upper_bound": None,
                "attr_type": None,
                "attr_default": None,
                "attr_notes": None,
                "attr_stereotype": None,
            }
        ]
        cls = parse_uml_class(class_rows)
        assert cls.stereotype == uml_model.ClassStereotype.ENUMERATION
        assert len(cls.attributes) == 0

    def test_parse_uml_project(self):
        pkg_rows = [
            {
                "id": 1,
                "name": "Base",
                "author": "",
                "parent_id": None,
                "created_date": None,
                "modified_date": None,
                "note": "",
            }
        ]
        class_rows = [
            {
                "class_id": 10,
                "class_name": "Substation",
                "class_author": "",
                "class_package_id": 1,
                "class_created_date": None,
                "class_modified_date": None,
                "class_note": "",
                "class_stereotype": None,
                "attr_id": 101,
                "attr_name": "name",
                "attr_lower_bound": "1",
                "attr_upper_bound": "1",
                "attr_type": "String",
                "attr_default": None,
                "attr_notes": "",
                "attr_stereotype": None,
            },
            {
                "class_id": 20,
                "class_name": "Equipment",
                "class_author": "",
                "class_package_id": 1,
                "class_created_date": None,
                "class_modified_date": None,
                "class_note": "",
                "class_stereotype": None,
                "attr_id": None,
                "attr_name": None,
                "attr_lower_bound": None,
                "attr_upper_bound": None,
                "attr_type": None,
                "attr_default": None,
                "attr_notes": None,
                "attr_stereotype": None,
            },
        ]
        rel_rows = [
            {
                "id": 99,
                "type": "Association",
                "start_object_id": 10,
                "end_object_id": 20,
                "direction": "Source -> Destination",
                "source_card": "1",
                "source_role": "Substation",
                "source_role_note": "",
                "dest_card": "0..*",
                "dest_role": "Equipment",
                "dest_role_note": "",
            },
            # Dangling relation pointing to non-existent class 999
            {
                "id": 100,
                "type": "Association",
                "start_object_id": 10,
                "end_object_id": 999,
                "direction": "Source -> Destination",
                "source_card": "1",
                "source_role": "",
                "source_role_note": "",
                "dest_card": "1",
                "dest_role": "",
                "dest_role_note": "",
            },
        ]

        proj = parse_uml_project(pkg_rows, class_rows, rel_rows)
        assert len(proj.packages.by_id) == 1
        assert len(proj.classes.by_id) == 2
        # Dangling relation was filtered out
        assert len(proj.relations.by_id) == 1
        assert 99 in proj.relations.by_id
        assert 100 not in proj.relations.by_id
