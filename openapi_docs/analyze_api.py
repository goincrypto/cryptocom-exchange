#!/usr/bin/env python3
"""
Analyze downloaded OpenAPI YAML files and generate summary for API implementation.
Extracts method names, request/response schemas, and generates code structure hints.
"""

import json
from pathlib import Path
import yaml

DOCS_DIR = Path("specs")


def analyze_yaml_file(filepath: Path) -> dict | None:
    """Parse a single YAML file and extract key information."""
    try:
        with open(filepath) as f:
            spec = yaml.safe_load(f)

        info = spec.get("info", {})
        title = info.get("title", filepath.stem)

        paths = spec.get("paths", {})
        schemas = {}

        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ["post", "get", "put", "delete"]:
                    # Extract request schema
                    request_body = details.get("requestBody", {})
                    content = request_body.get("content", {}).get(
                        "application/json", {}
                    )
                    request_schema = content.get("schema", {})

                    # Extract response schemas
                    responses = details.get("responses", {})
                    success_response = responses.get("200", {})
                    response_schema = (
                        success_response.get("content", {})
                        .get("application/json", {})
                        .get("schema", {})
                    )

                    schemas[method.upper()] = {
                        "path": path,
                        "summary": details.get("summary", ""),
                        "description": details.get("description", "")[:200] + "..."
                        if details.get("description", "")
                        else "",
                        "operationId": details.get("operationId", ""),
                        "requestRef": request_schema.get("$ref", ""),
                        "responseRef": response_schema.get("$ref", ""),
                    }

        return {
            "title": title,
            "schemas_location": spec.get("components", {}).get("schemas", {}),
            "methods": schemas,
            "servers": spec.get("servers", []),
        }

    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None


def main():
    """Analyze all YAML files and generate report."""
    yaml_files = list(DOCS_DIR.glob("*.yaml"))
    print(f"Analyzing {len(yaml_files)} YAML files...\n")

    all_endpoints = []
    all_schemas = {}

    for yaml_file in sorted(yaml_files):
        result = analyze_yaml_file(yaml_file)
        if result:
            filename = yaml_file.stem

            # Collect schemas (deduplicate by name)
            for schema_name, schema_def in result["schemas_location"].items():
                if schema_name not in all_schemas:
                    all_schemas[schema_name] = {
                        "source": filename,
                        "type": schema_def.get("type"),
                        "description": schema_def.get("description", "")[:150],
                        "properties": list(schema_def.get("properties", {}).keys())[
                            :10
                        ],  # First 10 props
                    }

            # Collect endpoints
            for method, details in result["methods"].items():
                all_endpoints.append(
                    {
                        "endpoint": filename,
                        "method": method,
                        "path": details["path"],
                        "summary": details["summary"],
                        "operation_id": details["operationId"],
                        "request_ref": details["requestRef"],
                        "response_ref": details["responseRef"],
                    }
                )

    # Print summary
    print("=" * 80)
    print("ENDPOINTS SUMMARY")
    print("=" * 80)

    # Group by prefix
    prefixes = {}
    for ep in all_endpoints:
        prefix = (
            ep["endpoint"].split("-")[0] + "-" + ep["endpoint"].split("-")[1]
            if "-" in ep["endpoint"]
            else ep["endpoint"]
        )
        if prefix not in prefixes:
            prefixes[prefix] = []
        prefixes[prefix].append(ep)

    for prefix, endpoints in sorted(prefixes.items()):
        print(f"\n{prefix} ({len(endpoints)} endpoints):")
        for ep in endpoints:
            print(f"  {ep['method']} {ep['path']}")
            print(f"    → {ep['summary']}")

    # Print unique schemas
    print("\n" + "=" * 80)
    print(f"SCHEMAS ({len(all_schemas)} total)")
    print("=" * 80)

    # Common patterns
    print("\nCommon Schema Patterns:")
    common_schemas = [
        k
        for k in all_schemas.keys()
        if any(
            x in k.lower()
            for x in ["order", "trade", "position", "balance", "response", "request"]
        )
    ]
    for schema in sorted(common_schemas)[:30]:
        info = all_schemas[schema]
        print(f"  - {schema}")
        print(f"      Type: {info['type']} | Source: {info['source']}")
        if info["properties"]:
            print(f"      Props: {', '.join(info['properties'][:8])}")

    # Output JSON for programmatic use
    output = {
        "endpoints": sorted(all_endpoints, key=lambda x: x["path"]),
        "schemas": all_schemas,
        "stats": {
            "total_endpoints": len(all_endpoints),
            "total_schemas": len(all_schemas),
            "files_processed": len(yaml_files),
        },
    }

    # Write summary to JSON
    with open("api_summary.json", "w") as f:
        json.dump(output, f, indent=2)

    print("\nFull summary written to this directory (api_summary.json)")
    print(f"Stats: {output['stats']}")


if __name__ == "__main__":
    main()
