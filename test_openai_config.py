#!/usr/bin/env python3
"""
Test script to verify OpenAI configuration and PDF processing capabilities
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

def test_config():
    """Test configuration loading"""
    print("=== Testing Configuration ===")
    try:
        from app.core.config import settings
        print("✓ Configuration loaded successfully")
        print(f"OpenAI API Key: {'Set' if settings.OPENAI_API_KEY != 'your-openai-api-key' else 'Not configured (using placeholder)'}")
        print(f"Database URL: {settings.DATABASE_URL}")
        print(f"Upload Directory: {settings.UPLOAD_DIR}")
        return True
    except Exception as e:
        print(f"✗ Error loading configuration: {e}")
        return False

def test_openai_import():
    """Test OpenAI import and client creation"""
    print("\n=== Testing OpenAI Import ===")
    try:
        import openai
        print("✓ OpenAI library imported successfully")
        
        from app.core.config import settings
        if settings.OPENAI_API_KEY == "your-openai-api-key":
            print("⚠ Warning: OpenAI API key is set to placeholder value")
            print("  Please set a real OpenAI API key in the .env file")
            return False
        else:
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            print("✓ OpenAI client created successfully")
            return True
    except Exception as e:
        print(f"✗ Error with OpenAI: {e}")
        return False

def test_statement_parser():
    """Test statement parser initialization"""
    print("\n=== Testing Statement Parser ===")
    try:
        from app.services.statement_parser import StatementParser
        parser = StatementParser()
        print("✓ Statement parser initialized successfully")
        return True
    except Exception as e:
        print(f"✗ Error initializing statement parser: {e}")
        return False

def test_pdf_file():
    """Test if PDF file exists and can be read"""
    print("\n=== Testing PDF File ===")
    pdf_path = "EECC_VISA_unlocked.pdf"
    if os.path.exists(pdf_path):
        print(f"✓ PDF file found: {pdf_path}")
        try:
            with open(pdf_path, 'rb') as file:
                content = file.read()
                print(f"✓ PDF file readable, size: {len(content)} bytes")
                return True
        except Exception as e:
            print(f"✗ Error reading PDF file: {e}")
            return False
    else:
        print(f"✗ PDF file not found: {pdf_path}")
        return False

def main():
    """Run all tests"""
    print("Testing Personal CFO Backend Configuration\n")
    
    tests = [
        test_config,
        test_openai_import,
        test_statement_parser,
        test_pdf_file
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            results.append(False)
    
    print("\n=== Summary ===")
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed! System ready for PDF processing.")
    else:
        print("⚠ Some tests failed. Please address the issues above.")
        if not results[1]:  # OpenAI test failed
            print("\nNext steps:")
            print("1. Get an OpenAI API key from https://platform.openai.com/api-keys")
            print("2. Update the OPENAI_API_KEY in your .env file")
            print("3. Re-run this test")

if __name__ == "__main__":
    main()
