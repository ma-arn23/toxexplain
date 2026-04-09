"""
build_drugbank_texts.py — one-time local extraction script.

Reads drugbank.xml + the curated Excel, extracts DrugBank text + SMILES for
each withdrawn drug, and writes a small JSON file (drugbank_texts.json) to be
shipped with the API. The runtime API never touches drugbank.xml directly —
it only reads this small JSON.

Run this ONCE on your laptop (the same way you ran drugbank_llm_pipeline.py),
then commit the resulting JSON to the repo.

USAGE:
    pip install pandas lxml openpyxl
    python build_drugbank_texts.py \\
        --xml /path/to/drugbank.xml \\
        --excel Withdrawn_Drugs_Mechanistic_Curation_Template.xlsx \\
        --output api/data/drugbank_texts.json
"""

import argparse
import json
import sys
import pandas as pd
from lxml import etree

NS = {"db": "http://www.drugbank.ca"}


def _get_text(elem, xpath):
    node = elem.find(xpath, NS)
    return node.text.strip() if node is not None and node.text else ""


def _parse_bond(bond_elem):
    """Parse a target/enzyme/transporter element from DrugBank XML."""
    poly = bond_elem.find("db:polypeptide", NS)
    data = {
        "name": _get_text(bond_elem, "db:name"),
        "known_action": _get_text(bond_elem, "db:known-action"),
        "actions": [],
        "gene_name": "",
    }
    for action in bond_elem.findall("db:actions/db:action", NS):
        if action.text:
            data["actions"].append(action.text)
    if poly is not None:
        data["gene_name"] = _get_text(poly, "db:gene-name")
    return data


def _format_drug_text(drug_data):
    """Format extracted XML fields into readable text for the LLM prompt."""
    sections = [
        f"Drug: {drug_data['drug_name']} ({drug_data['drug_id']})",
        f"Groups: {', '.join(drug_data['groups'])}",
    ]
    if drug_data["description"]:
        sections.append(f"\n--- Description ---\n{drug_data['description']}")
    if drug_data["indication"]:
        sections.append(f"\n--- Indication ---\n{drug_data['indication']}")
    if drug_data["mechanism_of_action"]:
        sections.append(f"\n--- Mechanism of Action ---\n{drug_data['mechanism_of_action']}")
    if drug_data["pharmacodynamics"]:
        sections.append(f"\n--- Pharmacodynamics ---\n{drug_data['pharmacodynamics']}")
    if drug_data["toxicity"]:
        sections.append(f"\n--- Toxicity ---\n{drug_data['toxicity']}")
    if drug_data["targets"]:
        sections.append("\n--- Targets ---")
        for t in drug_data["targets"]:
            actions = ", ".join(t["actions"]) if t["actions"] else "unknown"
            sections.append(
                f"  - {t['name']} (Gene: {t['gene_name']}) | Actions: {actions} "
                f"| Known action: {t['known_action']}"
            )
    if drug_data["enzymes"]:
        sections.append("\n--- Enzymes ---")
        for e in drug_data["enzymes"]:
            actions = ", ".join(e["actions"]) if e["actions"] else "unknown"
            sections.append(
                f"  - {e['name']} (Gene: {e['gene_name']}) | Actions: {actions} "
                f"| Known action: {e['known_action']}"
            )
    if drug_data["transporters"]:
        sections.append("\n--- Transporters ---")
        for t in drug_data["transporters"]:
            actions = ", ".join(t["actions"]) if t["actions"] else "unknown"
            sections.append(f"  - {t['name']} (Gene: {t['gene_name']}) | Actions: {actions}")
    return "\n".join(sections)


def _extract_drug(elem, db_id):
    """Pull all relevant fields out of one <drug> XML element."""
    drug_data = {
        "drug_id": db_id,
        "drug_name": _get_text(elem, "db:name"),
        "description": _get_text(elem, "db:description"),
        "mechanism_of_action": _get_text(elem, "db:mechanism-of-action"),
        "pharmacodynamics": _get_text(elem, "db:pharmacodynamics"),
        "toxicity": _get_text(elem, "db:toxicity"),
        "indication": _get_text(elem, "db:indication"),
        "groups": [],
        "targets": [],
        "enzymes": [],
        "transporters": [],
        "smiles": "",
    }
    for group in elem.findall("db:groups/db:group", NS):
        if group.text:
            drug_data["groups"].append(group.text)
    for target in elem.findall("db:targets/db:target", NS):
        drug_data["targets"].append(_parse_bond(target))
    for enzyme in elem.findall("db:enzymes/db:enzyme", NS):
        drug_data["enzymes"].append(_parse_bond(enzyme))
    for transporter in elem.findall("db:transporters/db:transporter", NS):
        drug_data["transporters"].append(_parse_bond(transporter))
    # SMILES from calculated-properties
    for prop in elem.findall("db:calculated-properties/db:property", NS):
        kind = prop.find("db:kind", NS)
        val = prop.find("db:value", NS)
        if kind is not None and kind.text == "SMILES" and val is not None:
            drug_data["smiles"] = val.text or ""
            break
    return drug_data


def _has_real_content(elem):
    """Filter out empty nested salt entries."""
    has_desc = bool(_get_text(elem, "db:description"))
    has_targets = elem.find("db:targets/db:target", NS) is not None
    has_enzymes = elem.find("db:enzymes/db:enzyme", NS) is not None
    return has_desc or has_targets or has_enzymes


def main():
    parser = argparse.ArgumentParser(description="Build drugbank_texts.json from drugbank.xml")
    parser.add_argument("--xml", required=True, help="Path to drugbank.xml")
    parser.add_argument("--excel", required=True,
                        help="Path to Withdrawn_Drugs_Mechanistic_Curation_Template.xlsx")
    parser.add_argument("--output", default="api/data/drugbank_texts.json",
                        help="Output JSON path")
    args = parser.parse_args()

    print(f"Reading curated drug list from {args.excel}...")
    overview = pd.read_excel(args.excel, sheet_name="Overview")
    wanted_ids = set(overview["drug_id"].dropna().astype(str).tolist())
    wanted_names = {
        str(name).strip().lower()
        for did, name in zip(overview["drug_id"], overview["drug_name"])
        if pd.isna(did) and pd.notna(name)
    }
    print(f"  {len(wanted_ids)} drugs by ID, {len(wanted_names)} drugs by name only")
    print(f"  IDs: {sorted(wanted_ids)}")
    print(f"  Names: {sorted(wanted_names)}")

    found_by_id: dict[str, dict] = {}
    found_by_name: dict[str, dict] = {}

    print(f"\nParsing {args.xml}... (this can take a couple of minutes)")
    context = etree.iterparse(args.xml, events=("end",), tag=f"{{{NS['db']}}}drug")

    for _, elem in context:
        db_id_elem = elem.find('db:drugbank-id[@primary="true"]', NS)
        if db_id_elem is None:
            elem.clear()
            continue
        db_id = db_id_elem.text

        name_elem = elem.find("db:name", NS)
        name = (name_elem.text or "").strip().lower() if name_elem is not None else ""

        match_by_id = db_id in wanted_ids and db_id not in found_by_id
        match_by_name = name in wanted_names and name not in found_by_name

        if not (match_by_id or match_by_name):
            elem.clear()
            continue

        if not _has_real_content(elem):
            elem.clear()
            continue

        drug_data = _extract_drug(elem, db_id)
        if match_by_id:
            found_by_id[db_id] = drug_data
            print(f"  ID match: {drug_data['drug_name']} ({db_id})")
        if match_by_name:
            found_by_name[name] = drug_data
            print(f"  Name match: {drug_data['drug_name']} ({db_id})")

        elem.clear()

        if len(found_by_id) == len(wanted_ids) and len(found_by_name) == len(wanted_names):
            break

    missing_ids = wanted_ids - set(found_by_id.keys())
    missing_names = wanted_names - set(found_by_name.keys())
    if missing_ids:
        print(f"\n  WARNING: Not found by ID: {sorted(missing_ids)}")
    if missing_names:
        print(f"  WARNING: Not found by name: {sorted(missing_names)}")

    # Build output records
    all_drugs = list(found_by_id.values()) + list(found_by_name.values())
    output_records = []
    for drug_data in all_drugs:
        if not drug_data["smiles"]:
            print(f"  WARNING: No SMILES for {drug_data['drug_name']}, skipping")
            continue
        output_records.append({
            "drug_id": drug_data["drug_id"],
            "drug_name": drug_data["drug_name"],
            "smiles": drug_data["smiles"],
            "drugbank_text": _format_drug_text(drug_data),
        })

    print(f"\nWriting {len(output_records)} records to {args.output}...")
    with open(args.output, "w") as f:
        json.dump(output_records, f, indent=2)
    print("Done.")

    print("\nSummary:")
    for rec in output_records:
        text_len = len(rec["drugbank_text"])
        print(f"  {rec['drug_name']:30s} | {rec['drug_id']:10s} | {text_len:6d} chars text")


if __name__ == "__main__":
    main()
