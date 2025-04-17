#!/usr/bin/env python3

import re
import sqlparse
import sqlglot
from typing import Optional

def extract_sql_from_text(text: str, original_query: str = "") -> str:
    """
    Extract SQL queries from text using sqlglot parser.
    Only SELECT statements are permitted.
    
    This function handles SQL in various formats:
    1. SQL in markdown code blocks (```sql ... ```)
    2. SQL directly in the text
    
    Args:
        text (str): The text that may contain SQL statements
        original_query (str): Optional fallback if no valid query is found
        
    Returns:
        str: The extracted and formatted SQL query
        
    Raises:
        ValueError: If no valid SQL query found or if query is not a SELECT statement
    """
    # Check if text contains SELECT
    if 'SELECT' not in text.upper():
        raise ValueError("No SELECT statement found in response")
    
    # Step 1: First try to extract from markdown code blocks
    sql_code_block_pattern = re.compile(r'```sql\s+(.*?)\s+```', re.DOTALL)
    matches = sql_code_block_pattern.findall(text)
    
    if matches:
        # Found SQL code block, extract and clean it
        for sql in matches:
            sql = sql.strip()
            # Try to parse with sqlglot to validate
            try:
                parsed = sqlglot.parse_one(sql)
                # Verify this is a SELECT statement
                if str(parsed).upper().startswith('SELECT'):
                    # Format and return
                    formatted = sqlparse.format(str(parsed), strip_comments=True).strip()
                    # Remove trailing semicolon if present
                    if formatted.endswith(';'):
                        formatted = formatted[:-1]
                    return formatted
            except Exception:
                # If parsing failed, continue to the next match
                continue
    
    # Step 2: Try to find SELECT statements in plain text
    # Find positions of all SELECT keywords
    select_positions = [m.start() for m in re.finditer(r'\bSELECT\b', text, re.IGNORECASE)]
    
    # Try each position, starting from the last one (often the most complete query)
    for pos in reversed(select_positions):
        # Extract text from SELECT keyword to end
        potential_sql = text[pos:]
        
        # Try to parse with sqlglot to validate it's proper SQL
        try:
            # Parse the SQL
            parsed = sqlglot.parse_one(potential_sql)
            
            # Verify this is a SELECT statement
            if not str(parsed).upper().startswith('SELECT'):
                continue
                
            # Format the SQL with sqlparse for consistency
            formatted = sqlparse.format(str(parsed), strip_comments=True).strip()
            
            # Remove trailing semicolon if present
            if formatted.endswith(';'):
                formatted = formatted[:-1]
                
            return formatted
            
        except Exception:
            # If parsing failed, continue to the next position
            continue
    
    # If we got here, no valid SQL was found
    if original_query and 'SELECT' in original_query.upper():
        # Use original query as fallback if provided
        query = original_query.strip()
        # Remove trailing semicolon if present
        if query.endswith(';'):
            query = query[:-1]
        return sqlparse.format(query, strip_comments=True).strip()
    
    # No valid SQL found
    raise ValueError("No valid SQL query found in response") 