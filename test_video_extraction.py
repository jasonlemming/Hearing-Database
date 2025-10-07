#!/usr/bin/env python3
"""
Test script for video URL extraction and YouTube ID parsing
"""
from parsers.hearing_parser import HearingParser
from fetchers.hearing_fetcher import HearingFetcher
from api.client import CongressAPIClient


def test_video_parsing():
    """Test video URL parsing logic"""
    print("=" * 60)
    print("Testing Video URL Parsing")
    print("=" * 60)

    parser = HearingParser(strict_mode=False)

    # Test cases
    test_cases = [
        {
            'name': 'Valid Congress.gov video URL',
            'url': 'https://www.congress.gov/committees/video/house-appropriations/hshm12/yv8VUIRAm7k',
            'expected_id': 'yv8VUIRAm7k'
        },
        {
            'name': 'Valid URL with trailing slash',
            'url': 'https://www.congress.gov/committees/video/senate-commerce/ssco00/dQw4w9WgXcQ/',
            'expected_id': 'dQw4w9WgXcQ'
        },
        {
            'name': 'Invalid YouTube ID (wrong length)',
            'url': 'https://www.congress.gov/committees/video/house-appropriations/hshm12/invalid',
            'expected_id': None
        },
        {
            'name': 'Empty URL',
            'url': None,
            'expected_id': None
        }
    ]

    all_passed = True
    for test in test_cases:
        result = parser.parse_video_url(test['url'])
        passed = result['youtube_video_id'] == test['expected_id']

        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"\n{status}: {test['name']}")
        print(f"  URL: {test['url']}")
        print(f"  Expected ID: {test['expected_id']}")
        print(f"  Actual ID: {result['youtube_video_id']}")

        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All video parsing tests passed!")
    else:
        print("✗ Some tests failed")
    print("=" * 60)

    return all_passed


def test_video_extraction():
    """Test video extraction from API response"""
    print("\n" + "=" * 60)
    print("Testing Video Extraction from API Response")
    print("=" * 60)

    # Create mock hearing fetcher
    class MockApiClient:
        pass

    fetcher = HearingFetcher(MockApiClient())

    # Test cases
    test_cases = [
        {
            'name': 'Videos as dict with item array',
            'hearing_data': {
                'videos': {
                    'item': [
                        {
                            'name': 'Test Video',
                            'url': 'https://www.congress.gov/committees/video/house-appropriations/hshm12/yv8VUIRAm7k'
                        }
                    ]
                }
            },
            'expected_url': 'https://www.congress.gov/committees/video/house-appropriations/hshm12/yv8VUIRAm7k'
        },
        {
            'name': 'Videos as array',
            'hearing_data': {
                'videos': [
                    {
                        'name': 'Test Video',
                        'url': 'https://www.congress.gov/committees/video/senate-commerce/ssco00/dQw4w9WgXcQ'
                    }
                ]
            },
            'expected_url': 'https://www.congress.gov/committees/video/senate-commerce/ssco00/dQw4w9WgXcQ'
        },
        {
            'name': 'No videos',
            'hearing_data': {},
            'expected_url': None
        },
        {
            'name': 'Empty videos',
            'hearing_data': {'videos': None},
            'expected_url': None
        }
    ]

    all_passed = True
    for test in test_cases:
        result = fetcher.extract_videos(test['hearing_data'])
        passed = result['video_url'] == test['expected_url']

        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"\n{status}: {test['name']}")
        print(f"  Expected URL: {test['expected_url']}")
        print(f"  Actual URL: {result['video_url']}")

        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All video extraction tests passed!")
    else:
        print("✗ Some tests failed")
    print("=" * 60)

    return all_passed


def main():
    """Run all tests"""
    print("\n🎬 YouTube Video Integration - Test Suite\n")

    parsing_passed = test_video_parsing()
    extraction_passed = test_video_extraction()

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"Video Parsing: {'✓ PASS' if parsing_passed else '✗ FAIL'}")
    print(f"Video Extraction: {'✓ PASS' if extraction_passed else '✗ FAIL'}")

    if parsing_passed and extraction_passed:
        print("\n🎉 All tests passed! Video integration is working correctly.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the output above.")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
