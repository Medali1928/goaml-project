"""Validate a generated goAML XML file against the provided XSD.

Usage:
    python tools/validate_goaml_xml.py path/to/file.xml path/to/goAMLSchemaNew.xsd

Note: the provided schema is XSD 1.1. lxml validates XSD 1.0 only, so this script
removes xs:assert nodes for a first technical validation pass. CTAF business rules
still need separate checks.
"""
from __future__ import annotations

import sys
from pathlib import Path
from lxml import etree

XS_NS = "http://www.w3.org/2001/XMLSchema"


def load_xsd_10_compatible(xsd_path: Path) -> etree.XMLSchema:
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(str(xsd_path), parser)
    root = tree.getroot()

    # lxml does not support XSD 1.1 assertions.
    for assertion in root.xpath("//xs:assert", namespaces={"xs": XS_NS}):
        assertion.getparent().remove(assertion)

    return etree.XMLSchema(root)


def validate(xml_path: Path, xsd_path: Path) -> int:
    xml_doc = etree.parse(str(xml_path))
    schema = load_xsd_10_compatible(xsd_path)

    if schema.validate(xml_doc):
        print("OK: XML passed XSD 1.0-compatible validation.")
        return 0

    print("FAILED: XML has schema errors:")
    for error in schema.error_log:
        print(f"- line {error.line}: {error.message}")
    return 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(validate(Path(sys.argv[1]), Path(sys.argv[2])))
