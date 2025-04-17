#!/usr/bin/env python3

import unittest
import sys
import os

# Add the src directory to the path to make imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from util.sql_parser import extract_sql_from_text

class TestSQLExtraction(unittest.TestCase):
    """Test cases for extracting SQL from markdown text."""
    
    def test_extract_from_code_block(self):
        """Test extracting SQL from a markdown code block."""
        markdown_text = """
Here's the SQL query to answer your question:

```sql
SELECT username, status 
FROM users 
WHERE status = 'partially_offboarded';
```

This will find all users with status 'partially_offboarded'.
"""
        expected = "SELECT username, status\nFROM users\nWHERE status = 'partially_offboarded'"
        result = extract_sql_from_text(markdown_text)
        # Replace newlines and multiple spaces with single spaces for comparison
        result_normalized = ' '.join(result.replace('\n', ' ').split())
        expected_normalized = ' '.join(expected.replace('\n', ' ').split())
        self.assertEqual(result_normalized, expected_normalized)
    
    def test_extract_from_mixed_content(self):
        """Test extracting SQL from text with explanation mixed in."""
        markdown_text = """
To find users that are partially offboarded, you can use the following SQL query:

```sql
SELECT * 
FROM users 
WHERE offboarding_status = 'partial'
```

This query searches the users table for the offboarding_status column.
"""
        expected = "SELECT * FROM users WHERE offboarding_status = 'partial'"
        result = extract_sql_from_text(markdown_text)
        # Replace newlines and multiple spaces with single spaces for comparison
        result_normalized = ' '.join(result.replace('\n', ' ').split())
        expected_normalized = ' '.join(expected.replace('\n', ' ').split())
        self.assertEqual(result_normalized, expected_normalized)
    
    def test_extract_from_complex_text(self):
        """Test extracting SQL from complex text with explanatory content."""
        markdown_text = """
Let me analyze what we're looking for. The question asks about partially offboarded users.

I'll create a SELECT statement that queries the users table:

SELECT * FROM users WHERE offboarding_status = 'partial' OR status LIKE '%partial%';
"""
        # Don't check for exact formatting - normalize both by removing whitespace
        result = extract_sql_from_text(markdown_text)
        # Replace newlines and multiple spaces with single spaces for comparison
        expected_normalized = "SELECT * FROM users WHERE offboarding_status = 'partial' OR status LIKE '%partial%'"
        result_normalized = ' '.join(result.replace('\n', ' ').split())
        expected_normalized = ' '.join(expected_normalized.replace('\n', ' ').split())
        self.assertEqual(result_normalized, expected_normalized)
        
    def test_no_sql_found(self):
        """Test handling when no SQL is found."""
        markdown_text = "This text doesn't contain any SQL queries."
        with self.assertRaises(ValueError):
            extract_sql_from_text(markdown_text)

if __name__ == "__main__":
    unittest.main() 