#!/usr/bin/env python3
"""Script to export OpenAPI schema for PetMarket API."""
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.main import app

def export_openapi():
    """Export the OpenAPI schema to a JSON file."""
    openapi_schema = app.openapi()

    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "api", "openapi.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)

    print(f"✓ OpenAPI schema exported to {output_path}")

if __name__ == "__main__":
    export_openapi()