"""
Pre-deployment check for every PBIP project in the portfolio.

  * every JSON file in the report and semantic model folders parses
  * every report points at a semantic model folder that exists
  * every field a visual uses (table, column or measure) exists in the TMDL

Run it locally or in CI before publishing:  python check_pbip.py <portfolio folder>
Exit code is the number of problems found, so a CI step fails on any error.
"""
import json, os, re, sys

root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..")


def unq(name):
    name = name.strip()
    return name[1:-1].replace("''", "'") if name.startswith("'") else name


def model_fields(definition):
    fields = {}
    for f in os.listdir(os.path.join(definition, "tables")):
        table, names = None, set()
        for line in open(os.path.join(definition, "tables", f), encoding="utf-8"):
            m = re.match(r"^table (.+)$", line.rstrip())
            if m:
                table = unq(m.group(1))
            m = re.match(r"^\t(column|measure|calculationGroup) ?(.*?)(\s*=.*)?$", line.rstrip("\n"))
            if m and m.group(2):
                names.add(unq(m.group(2)))
        fields[table] = names
    return fields


def field_refs(node):
    if isinstance(node, dict):
        for kind in ("Column", "Measure", "Aggregation", "HierarchyLevel"):
            v = node.get(kind)
            if isinstance(v, dict) and "Property" in v:
                ent = v.get("Expression", {}).get("SourceRef", {}).get("Entity")
                if ent:
                    yield ent, v["Property"]
        for v in node.values():
            yield from field_refs(v)
    elif isinstance(node, list):
        for v in node:
            yield from field_refs(v)


problems = 0
for pbip in sorted(p for d, _, fs in os.walk(root) for p in (os.path.join(d, f) for f in fs) if p.endswith(".pbip")):
    proj = os.path.dirname(pbip)
    name = os.path.basename(pbip)[:-5]
    report, model = os.path.join(proj, name + ".Report"), os.path.join(proj, name + ".SemanticModel")
    pbir = json.load(open(os.path.join(report, "definition.pbir"), encoding="utf-8"))
    target = os.path.normpath(os.path.join(report, pbir["datasetReference"]["byPath"]["path"]))
    if not os.path.isdir(target):
        print(f"{name}: report points at missing model {target}")
        problems += 1
    fields = model_fields(os.path.join(model, "definition"))
    checked = 0
    for d, _, fs in os.walk(proj):
        for f in fs:
            if not f.endswith(".json") or os.sep + "data" + os.sep in d + os.sep:
                continue
            path = os.path.join(d, f)
            try:
                doc = json.load(open(path, encoding="utf-8"))
            except ValueError as e:
                print(f"{name}: {os.path.relpath(path, proj)} is not valid JSON ({e})")
                problems += 1
                continue
            if f == "visual.json":
                for table, prop in field_refs(doc):
                    checked += 1
                    if prop not in fields.get(table, ()):
                        print(f"{name}: {os.path.relpath(path, proj)} uses {table}[{prop}], which is not in the model")
                        problems += 1
    print(f"{name}: {len(fields)} tables, {checked} field references checked")
print(f"{problems} problem(s)")
sys.exit(problems)
