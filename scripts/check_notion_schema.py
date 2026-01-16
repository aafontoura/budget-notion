#!/usr/bin/env python3
"""Check Notion database schema and show all properties."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from notion_client import Client
from config.settings import settings


def check_notion_schema():
    """Retrieve and display Notion database schema."""
    try:
        # Get credentials
        token = settings.get_notion_token()
        database_id = settings.get_notion_database_id()

        print("=" * 60)
        print("Notion Database Schema Check")
        print("=" * 60)
        print()

        # Connect to Notion
        client = Client(auth=token)

        # Retrieve database
        database = client.databases.retrieve(database_id=database_id)

        # Get database title
        title_objects = database.get('title', [])
        database_title = title_objects[0].get('plain_text', 'Untitled') if title_objects else 'Untitled'

        print(f"Database Title: {database_title}")
        print(f"Database ID: {database_id}")
        print()
        print("=" * 60)
        print("Properties:")
        print("=" * 60)

        # Get properties - Notion API v2022-06-28 format
        properties = database.get("properties", {})

        # Debug: show raw response if no properties found
        if not properties:
            print("\nDEBUG: Raw database response keys:", list(database.keys()))
            print("DEBUG: Full response:", database)

        if not properties:
            print("❌ No properties found in database!")
            return

        # Display each property
        for prop_name, prop_info in properties.items():
            prop_type = prop_info.get("type", "unknown")

            print(f"\n✓ {prop_name}")
            print(f"  Type: {prop_type}")

            # Show additional info for select properties
            if prop_type == "select" and "select" in prop_info:
                options = prop_info["select"].get("options", [])
                if options:
                    print(f"  Options: {', '.join([opt['name'] for opt in options])}")

        print()
        print("=" * 60)
        print("Expected Properties (from code):")
        print("=" * 60)
        print()

        expected = {
            "Description": "title",
            "Date": "date",
            "Amount": "number",
            "Category": "select",
            "Account": "select",
            "Notes": "text or rich_text",
            "Reviewed": "checkbox",
            "Transaction ID": "text or rich_text",
            "AI Confidence": "number",
        }

        for prop_name, prop_type in expected.items():
            if prop_name in properties:
                actual_type = properties[prop_name].get("type")
                if prop_type == "text or rich_text":
                    match = actual_type in ["text", "rich_text"]
                else:
                    match = actual_type == prop_type

                if match:
                    print(f"✓ {prop_name}: {actual_type}")
                else:
                    print(f"⚠️  {prop_name}: Expected {prop_type}, found {actual_type}")
            else:
                print(f"❌ {prop_name}: MISSING")

        print()
        print("=" * 60)
        print("Recommendations:")
        print("=" * 60)
        print()

        # Check for common issues
        if "Description" not in properties:
            if "Name" in properties:
                print("⚠️  Found 'Name' instead of 'Description'")
                print("   Solution: Rename 'Name' property to 'Description' in Notion")
                print("   OR: Update code to use 'Name' instead of 'Description'")
            else:
                print("❌ No title property found!")
                print("   Solution: Add a 'Description' property of type Title")

        missing = [p for p in expected if p not in properties]
        if missing:
            print()
            print(f"Missing properties: {', '.join(missing)}")
            print("See docs/NOTION_SCHEMA.md for setup instructions")

    except Exception as e:
        print(f"❌ Error: {e}")
        print()
        print("Common issues:")
        print("1. Check NOTION_TOKEN in .env file")
        print("2. Check NOTION_DATABASE_ID in .env file")
        print("3. Ensure integration has access to database")
        print("4. See docs/NOTION_SCHEMA.md for setup guide")
        sys.exit(1)


if __name__ == "__main__":
    check_notion_schema()
