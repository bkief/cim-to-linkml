from pathlib import Path
import sqlite3
import pytest

from cim_to_linkml.read import (
    read_uml_project,
    read_uml_packages,
    read_uml_classes,
    read_uml_relations,
)
from cim_to_linkml.parser import parse_uml_project
import cim_to_linkml.uml_model as uml_model


from typing import Generator

@pytest.fixture
def mock_ea_sqlite_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()

    # Create EA t_package table
    cur.execute(
        """
        CREATE TABLE t_package (
            Package_ID INTEGER PRIMARY KEY,
            Name TEXT,
            Parent_ID INTEGER,
            CreatedDate TEXT,
            ModifiedDate TEXT
        )
        """
    )
    # Create EA t_object table
    cur.execute(
        """
        CREATE TABLE t_object (
            Object_ID INTEGER PRIMARY KEY,
            Package_ID INTEGER,
            Name TEXT,
            Author TEXT,
            Object_Type TEXT,
            CreatedDate TEXT,
            ModifiedDate TEXT,
            Stereotype TEXT,
            Note TEXT
        )
        """
    )
    # Create EA t_attribute table
    cur.execute(
        """
        CREATE TABLE t_attribute (
            ID INTEGER PRIMARY KEY,
            Object_ID INTEGER,
            Name TEXT,
            LowerBound TEXT,
            UpperBound TEXT,
            Type TEXT,
            Notes TEXT,
            Stereotype TEXT,
            "Default" TEXT
        )
        """
    )
    # Create EA t_connector table
    cur.execute(
        """
        CREATE TABLE t_connector (
            Connector_ID INTEGER PRIMARY KEY,
            Connector_Type TEXT,
            Start_Object_ID INTEGER,
            End_Object_ID INTEGER,
            Direction TEXT,
            SubType TEXT,
            SourceCard TEXT,
            SourceRole TEXT,
            SourceRoleNote TEXT,
            DestCard TEXT,
            DestRole TEXT,
            DestRoleNote TEXT
        )
        """
    )

    # Insert test package
    cur.execute(
        "INSERT INTO t_package VALUES (1, 'Core', 0, '2026-01-01', '2026-01-02')"
    )
    cur.execute(
        "INSERT INTO t_object (Object_ID, Package_ID, Name, Object_Type, Note) VALUES (1, 0, 'Core', 'Package', 'Core package')"
    )

    # Insert test class
    cur.execute(
        "INSERT INTO t_object (Object_ID, Package_ID, Name, Author, Object_Type, Stereotype, Note) VALUES (10, 1, 'Terminal', 'TC57', 'Class', NULL, 'Terminal node')"
    )
    cur.execute(
        "INSERT INTO t_attribute VALUES (101, 10, 'connected', '0', '1', 'Boolean', 'Whether connected', NULL, 'true')"
    )

    # Insert another class
    cur.execute(
        "INSERT INTO t_object (Object_ID, Package_ID, Name, Author, Object_Type, Stereotype, Note) VALUES (20, 1, 'ConnectivityNode', 'TC57', 'Class', NULL, 'Connectivity node')"
    )

    # Insert connector
    cur.execute(
        """
        INSERT INTO t_connector VALUES (
            1001, 'Association', 10, 20, 'Source -> Destination', 'Weak',
            '1', 'Terminal', 'Terminal role', '0..1', 'ConnectivityNode', 'Node role'
        )
        """
    )

    conn.commit()
    yield conn
    conn.close()


class TestReadQea:
    def test_read_mock_ea_sqlite(self, mock_ea_sqlite_conn: sqlite3.Connection):
        pkg_results, class_results, rel_results = read_uml_project(mock_ea_sqlite_conn)
        project = parse_uml_project(pkg_results, class_results, rel_results)

        assert isinstance(project, uml_model.Project)
        assert len(project.packages.by_id) == 1
        assert "Core" in project.packages.by_qualified_name

        assert len(project.classes.by_id) == 2
        terminal = project.classes.by_name.get("Terminal")
        assert terminal is not None
        assert len(terminal.attributes) == 1
        assert terminal.attributes[0].name == "connected"

        assert len(project.relations.by_id) == 1

    def test_read_actual_qea_file_if_present(self, data_dir: Path):
        qea_files = sorted(data_dir.rglob("*.qea"))
        if not qea_files:
            pytest.skip("No .qea files found in data directory")

        qea_path = qea_files[0]
        with sqlite3.connect(qea_path) as conn:
            pkg_results, class_results, rel_results = read_uml_project(conn)
            project = parse_uml_project(pkg_results, class_results, rel_results)
            assert len(project.packages.by_id) > 0
            assert len(project.classes.by_id) > 0
            assert any("TC57CIM" in name for name in project.packages.by_qualified_name)
