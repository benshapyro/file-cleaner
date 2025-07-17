#!/usr/bin/env python3
"""Test script to verify structured outputs implementation"""

import json
from openai import OpenAI
from dotenv import load_dotenv
import os
from config import AI_MODEL, AI_RESPONSE_SCHEMA

# Load environment variables
load_dotenv()

def test_structured_outputs():
    """Test the structured outputs with a sample request"""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Sample files for testing
    test_files = """
- installer_2024.dmg (150 MB, 45 days old, type: installer)
- report_draft.docx (2.3 MB, 3 days old, type: document)
- screenshot_2024-01-15.png (500 KB, 90 days old, type: image)
- cache_temp_file.tmp (10 KB, 60 days old, type: unknown)
- important_contract.pdf (5 MB, 10 days old, type: document)
"""
    
    prompt = f"""Analyze these files from a Downloads folder and categorize each one.
Consider file age, type, and name patterns. Provide confidence score (0-1) and reasoning.

Categories:
- safe_to_delete: temporary files, old downloads, cache files, installers over 30 days old
- might_be_important: documents that might be needed, recent work files
- keep: clearly important files, personal documents, active projects

Files to analyze:
{test_files}"""

    print(f"Using model: {AI_MODEL}")
    print("Testing structured outputs...")
    
    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert file organization assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "file_categorization",
                    "strict": True,
                    "schema": AI_RESPONSE_SCHEMA
                }
            }
        )
        
        result = json.loads(response.choices[0].message.content)
        print("\nResponse received successfully!")
        print(json.dumps(result, indent=2))
        
        # Verify structure
        categorizations = result.get("categorizations", {})
        print(f"\nAnalyzed {len(categorizations)} files:")
        for filename, info in categorizations.items():
            print(f"- {filename}: {info['category']} (confidence: {info['confidence']:.0%})")
            print(f"  Reason: {info['reason']}")
        
    except Exception as e:
        print(f"Error: {e}")
        print(f"Error type: {type(e).__name__}")

if __name__ == "__main__":
    test_structured_outputs() 