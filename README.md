# cim-to-linkml

Generates [LinkML](https://linkml.io) schemas from the IEC Common Information Model (CIM).

## Supported input formats

| Format | Extensions | Notes |
| :--- | :--- | :--- |
| Sparx Enterprise Architect database | `.qea`, `.qeax` | Most complete source: dates, authors, notes, stereotypes and connector details. |
| XMI 1.1 / XMI 2.1 (EA export) | `.xmi`, `.xml` | Version is detected automatically. EA's `xmi:Extension` data (stereotypes, documentation, initial values) is used for XMI 2.1. |
| RDF Schema / OWL / Turtle profiles | `.rdf`, `.rdfs`, `.owl`, `.ttl` | CIM profiles such as CGMES (RDFS2020) or CIMTool output. Packages come from `cims:belongsToCategory`. |

QEA, XMI 1.1 and XMI 2.1 exports of the same CIM release yield equivalent models (this is covered by
`tests/test_model_consistency.py`).

## Installation
Make sure you have Python (≥ 3.11) and uv installed.

Run `uv sync` to have it set up a virtual environment for you with the necessary dependencies installed and configuration taken care of.

## Running `cim2linkml`

#### From within the virtual environment
Activate your virtual environment, and you should be able to use the `cim2linkml` script.

```
$ .venv\Scripts\activate  # On Windows
$ source .venv/bin/activate # On Unix/macOS
$ cim2linkml --help
# ...
```

#### Using `uv run`
You can also run the script inside the virtual environment without activating it.

```
$ uv run cim2linkml --help
# ...
```


### Usage
```
Usage: cim2linkml [OPTIONS] CIM_MODEL

  Generates LinkML schemas from the supplied Sparx EA QEA database, XMI file,
  or RDF/OWL/TTL ontology.

  You can specify which packages in the UML model to generate schemas from
  using the `--package` parameter, where you provide the fully qualified
  package name (e.g. `TC57CIM.IEC61970.Base.Core') of the package to select
  it.

  If the specified package is a leaf package, a single schema file will be
  generated.

  If the provided package is a non-leaf package, by default its subpackages
  are included and a schema file per package is created. A single schema file
  can also be created by passing `--single-schema'. Finally, it's possible to
  ignore all subpackages and create a single schema file just for the
  specified package alone. To achieve this, pass `--ignore-subpackages`.

Options:
  -p, --package TEXT     Fully qualified package name, or a unique suffix of
                         one (e.g. `IEC61970.Base.Core').  [default: TC57CIM]
  --single-schema        If true, a single schema is created, a schema per
                         package otherwise.
  --ignore-subpackages   If passed, all subpackages of the provided package
                         are ignored, i.e. only the package itself is
                         selected.
  -o, --output-dir PATH  Directory where schemas will be outputted.  [default:
                         schemas]
  --help                 Show this message and exit.
```

### Selecting packages

Package names are dot-separated paths from the model root. Enterprise Architect models nest everything under a
`Model` root package, so the fully qualified name of the Wires package is `Model.TC57CIM.IEC61970.Base.Wires`.
You don't have to type the whole path: any **unique suffix** is accepted, so `-p IEC61970.Base.Wires` or
`-p Wires` work too. A name that is ambiguous or unknown is rejected and the available packages are listed.

The default package is `TC57CIM`, the root of the CIM up to and including CIM17. **CIM18 renamed its root package to
`CIM`**, so pass `-p CIM` (or a subpackage) for CIM18 models.

RDF/OWL/TTL profiles are usually a single package (e.g. `TopologyProfile`); when there is only one package the
default selects it automatically.

### Output

In schema-per-package mode, files mirror the package hierarchy, e.g.
`schemas/Model/TC57CIM/IEC61970/Base/Wires.yml`. With `--single-schema` (or for a leaf package) a single file named
after the qualified package name is written, e.g. `schemas/Model.TC57CIM.IEC61970.Base.Wires.yml`.

Every schema is **self-contained**: besides the classes of the selected package(s) it includes all classes and
enumerations they depend on (superclasses, attribute types and associated classes, transitively). Schemas of
large packages can therefore be several megabytes.

Generated classes carry these annotations when available:

| Annotation | Meaning |
| :--- | :--- |
| `cim_version` | Version from the nearest `*CIMVersion` class (e.g. `IEC61970CIM17v40`). |
| `cim_specification` | Standard the package belongs to: `IEC 61970-301`, `IEC 61968-11` or `IEC 62325-301`. |
| `represents_cim_data_type` | Present on `<<CIMDatatype>>` classes. |

CIM primitive types map to LinkML types as follows:

| CIM | LinkML |
| :--- | :--- |
| `String`, `Duration`, `MonthDay`, `UUID` | `string` |
| `Boolean` | `boolean` |
| `Integer` | `integer` |
| `Float` | `float` |
| `Decimal` | `decimal` |
| `Date` / `DateTime` / `Time` | `date` / `datetime` / `time` |
| `URI`, `IRI` | `uri` |

An attribute whose type can't be resolved falls back to `string` with a warning.

### Examples

#### The entire CIM

##### Schema per package
If no package is specified, it defaults to TC57CIM, i.e. the entire CIM (up to CIM17). For non-leaf
packages like this one, the default behavior is to generate a schema for each subpackage.

```shell
$ cim2linkml data/cim.qea
```

For CIM18:

```shell
$ cim2linkml data/cim18.qea -p CIM
```

##### Single schema
If generating a single schema file is desired, this can be done as follows:

```shell
$ cim2linkml data/cim.qea --single-schema
```

#### Leaf package
Leaf packages by definition don't have subpackages and therefore always become a single schema.

```shell
$ cim2linkml data/cim.qea -p TC57CIM.IEC61970.Base.Wires
```

#### Non-leaf package

##### Including subpackages
By default, when providing a non-leaf package, all subpackages are included and schema files are
created for each package.

```shell
$ cim2linkml data/cim.qea -p TC57CIM.IEC61970
```

If a single schema file is desired, `--single-schema` can be passed.

##### Ignoring subpackages
If only selecting the package itself is desired, i.e. not including subpackages, one can pass `--ignore-subpackages`.
Note that in this case, it is always a single schema file (`--single-schema` is implied).

```shell
$ cim2linkml data/cim.qea -p TC57CIM.IEC61970 --ignore-subpackages
```

#### XMI and RDF profiles

```shell
$ cim2linkml data/cim17_XMI21.xmi -p IEC61970.Base.Core
$ cim2linkml tests/data/CGMES_Topology_RDFS2020.rdfs
```

### Validating the output

The generated schemas can be checked with LinkML's own tooling, for example:

```shell
$ uvx --from linkml linkml-lint schemas/Model.TC57CIM.IEC61970.Base.Wires.yml
```

Expect only warnings: CIM naming (e.g. association ends named `Terminal`) doesn't follow LinkML's naming
conventions.

## Known limitations

- **Duplicate class names** (a few exist in the CIM, e.g. `TroubleReportingKind`): one class is chosen and the others
  are skipped, with a warning.
- **CIMTool-style OWL profiles** that define properties through `owl:Restriction`s instead of `rdfs:domain` produce
  classes without attributes or associations. RDFS (e.g. CGMES RDFS2020) profiles are fully supported.
- **Slot name clashes**: if an attribute and an association end on the same class share a name, the association end
  wins silently.

## Development

```shell
$ uv sync
$ uv run pytest
```

The large Enterprise Architect test models under `tests/data/cim15`–`cim18` are committed as `.xz` archives and
decompressed automatically on the first test run. See [tests/data/README.md](tests/data/README.md) for the sources
of the test models.
