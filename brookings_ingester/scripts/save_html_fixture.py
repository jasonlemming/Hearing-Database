#!/usr/bin/env python3
"""
Save HTML Fixture - Fetch and save HTML content for testing

This script fetches HTML content from a URL and saves it as a test fixture.
Useful for creating regression tests without hitting live sites repeatedly.

Usage:
    python brookings_ingester/scripts/save_html_fixture.py <source_name> <url> [--output path]

Examples:
    # Save Heritage article
    python brookings_ingester/scripts/save_html_fixture.py heritage \\
        "https://www.heritage.org/education/commentary/school-choice-works" \\
        --output tests/fixtures/heritage_school_choice.html

    # Save AEI report (auto-generate filename)
    python brookings_ingester/scripts/save_html_fixture.py aei \\
        "https://www.aei.org/articles/economic-policy-2025/"
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse
import re

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def load_ingester(source_name: str):
    """Dynamically load ingester class by source name"""
    try:
        # Convert source_name to class name
        class_name = ''.join(word.capitalize() for word in source_name.split('_')) + 'Ingester'
        module_path = f'brookings_ingester.ingesters.{source_name}'

        module = __import__(module_path, fromlist=[class_name])
        ingester_class = getattr(module, class_name)
        return ingester_class()
    except (ImportError, AttributeError) as e:
        print(f"❌ Error loading ingester '{source_name}': {e}")
        sys.exit(1)


def generate_filename(source_name: str, url: str) -> str:
    """Generate a reasonable filename from URL"""
    parsed = urlparse(url)
    path = parsed.path.strip('/')

    # Extract last segment or slug
    if path:
        # Get last meaningful part
        parts = [p for p in path.split('/') if p]
        slug = parts[-1] if parts else 'index'

        # Clean up slug
        slug = re.sub(r'[^\w\-]', '_', slug)
        slug = slug[:50]  # Limit length

        return f"{source_name}_{slug}.html"
    else:
        return f"{source_name}_index.html"


def main():
    parser = argparse.ArgumentParser(
        description='Fetch and save HTML content as test fixture',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Save with custom filename
  python brookings_ingester/scripts/save_html_fixture.py heritage \\
      "https://www.heritage.org/education/commentary/school-choice" \\
      --output tests/fixtures/heritage_school_choice.html

  # Auto-generate filename
  python brookings_ingester/scripts/save_html_fixture.py aei \\
      "https://www.aei.org/articles/economic-policy/"

  # Save to custom directory
  python brookings_ingester/scripts/save_html_fixture.py brookings \\
      "https://www.brookings.edu/articles/foreign-policy/" \\
      --output /tmp/brookings_test.html
        """
    )

    parser.add_argument('source_name', help='Name of the source/ingester')
    parser.add_argument('url', help='URL to fetch')
    parser.add_argument('--output', '-o', help='Output file path (default: auto-generated in tests/fixtures/)')

    args = parser.parse_args()

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        # Auto-generate in tests/fixtures/
        fixtures_dir = project_root / 'tests' / 'fixtures'
        fixtures_dir.mkdir(parents=True, exist_ok=True)

        filename = generate_filename(args.source_name, args.url)
        output_path = fixtures_dir / filename

    print(f"🌐 Fetching: {args.url}")
    print(f"📦 Using ingester: {args.source_name}")

    # Load ingester
    ingester = load_ingester(args.source_name)

    # Fetch content
    try:
        print(f"⏳ Fetching content...")

        # Generate document_identifier from URL
        slug = generate_filename(args.source_name, args.url).replace(f"{args.source_name}_", "").replace(".html", "")

        # Use ingester's fetch method
        doc_meta = {
            'url': args.url,
            'document_identifier': slug
        }
        fetched = ingester.fetch(doc_meta)

        if not fetched or 'html_content' not in fetched:
            print(f"❌ Failed to fetch content from {args.url}")
            sys.exit(1)

        html_content = fetched['html_content']

        # Save to file
        print(f"💾 Saving to: {output_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Print stats
        size_kb = len(html_content) / 1024
        print(f"\n✅ Success!")
        print(f"   File: {output_path}")
        print(f"   Size: {size_kb:.1f} KB")
        print(f"   Lines: {html_content.count(chr(10))}")

        # Test parsing
        print(f"\n🧪 Testing parser...")
        try:
            parsed = ingester.parse(doc_meta, fetched)

            if parsed:
                print(f"   ✅ Parsing successful")
                print(f"   Title: {parsed.get('title', 'N/A')[:60]}")
                print(f"   Authors: {', '.join(parsed.get('authors', []))[:60]}")
                print(f"   Date: {parsed.get('publication_date', 'N/A')}")
                print(f"   Word count: {parsed.get('word_count', 0)}")
                print(f"   Content length: {len(parsed.get('full_text', ''))} chars")
            else:
                print(f"   ⚠️  Parser returned None")

        except Exception as e:
            print(f"   ❌ Parsing failed: {e}")

        # Suggest test code
        print(f"\n💡 Use this fixture in tests:")
        print(f"""
    def test_{args.source_name}_parsing():
        with open('{output_path}', 'r', encoding='utf-8') as f:
            html_content = f.read()

        parser = {args.source_name.capitalize()}HTMLParser()
        parsed = parser.parse(html_content, '{args.url}')

        assert parsed is not None
        assert parsed.title
        assert parsed.text_content
        # Add more assertions...
        """)

    except KeyboardInterrupt:
        print(f"\n\n⚠️  Interrupted by user")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
