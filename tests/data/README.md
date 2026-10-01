# CIM Test Models

This directory contains openly available Common Information Model (CIM) models across RDFS, OWL, and Turtle formats for testing and validation.

## Models Overview

| Filename | Format | Source / Standard | Description |
| :--- | :--- | :--- | :--- |
| `DistributionNetwork.rdfs` | RDFS (XML) | IEC 61968 / 61970 (`bressanmarcos/cimrdf.py`) | Distribution network model with `Wires`, `Core`, `Domain`, `Feeder`, `ConnectivityNode`, `Terminal`, `ACLineSegment`. |
| `CGMES_Topology_RDFS2020.rdfs` | RDFS2020 (XML) | ENTSO-E CGMES v3.0 / IEC 61970-600-2 | Official CGMES Topology profile describing TopologicalNode, Terminal, ConnectivityNodeContainer, etc. |
| `CGMES_EquipmentBoundary_RDFS2020.rdfs` | RDFS2020 (XML) | ENTSO-E CGMES v3.0 / IEC 61970-600-2 | Official CGMES Equipment Boundary profile for cross-border grid exchange. |
| `CGMES_GeographicalLocation_RDFS2020.rdfs` | RDFS2020 (XML) | ENTSO-E CGMES v3.0 / IEC 61970-600-2 | Official CGMES Geographical Location profile for coordinate and layout references. |
| `DMP_profile_IEC61970-457.rdfs` | RDFS2020 (XML) | CIMug (`cimug-org/cim-profiles`) | Detailed Model Parameterisation IEC 61970-457:2023 dynamics and parameter profile. |
| `cpsm2007.owl` | OWL (RDF/XML) | UCAIug CIMTool test suite | Common Power System Model (CPSM 2007) transmission profile with 89+ classes and associations. |
| `SampleProfile.owl` | OWL (RDF/XML) | UCAIug CIMTool (`CSharpEFTestProject`) | Compact sample profile including classes, attributes, and enumerations. |
| `CGMES_Topology.owl` | OWL (RDF/XML) | CIMug CGMES CIM17 (`cimug-org/CGMES-CIM17`) | Official CIM17 OWL serialization of the CGMES Topology profile. |
| `CGMES_EquipmentBoundary.owl` | OWL (RDF/XML) | CIMug CGMES CIM17 (`cimug-org/CGMES-CIM17`) | Official CIM17 OWL serialization of the CGMES Equipment Boundary profile. |
| `simple_substation.ttl` | Turtle (TTL) | Custom IEC 61970 sample | Compact test fixture with Substation, Equipment, attributes, and associations. |

## Compressed models

The large Enterprise Architect exports under `cim15/`–`cim18/` (`.qea`, `.xmi`) are committed as `.xz`. `tests/conftest.py` decompresses them next to the archives on first test run; the expanded files are git-ignored.
