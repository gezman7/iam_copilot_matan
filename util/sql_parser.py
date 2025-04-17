#!/usr/bin/env python3

import re
import sqlparse
import sqlglot
from typing import Optional

def extract_sql_from_text( original_query: str) -> str:
    sql_code_block_pattern = re.compile(r'```sql\s+(.*?)\s+```', re.DOTALL)
    matches = sql_code_block_pattern.findall(original_query)
    
    if matches:
        for sql in matches:
            sql = sql.strip()
            try:
                parsed = sqlglot.parse_one(sql)
                if str(parsed).upper().startswith('SELECT'):
                    formatted = sqlparse.format(str(parsed), strip_comments=True).strip()
                    if formatted.endswith(';'):
                        formatted = formatted[:-1]
                    return formatted
            except Exception:
                continue
    
    select_positions = [m.start() for m in re.finditer(r'\bSELECT\b', original_query, re.IGNORECASE)]
    
    for pos in reversed(select_positions):
        potential_sql = original_query[pos:]
        
        try:
            parsed = sqlglot.parse_one(potential_sql)
            
            if not str(parsed).upper().startswith('SELECT'):
                continue
                
            formatted = sqlparse.format(str(parsed), strip_comments=True).strip()
            
            if formatted.endswith(';'):
                formatted = formatted[:-1]
                
            return formatted
            
        except Exception:
            continue
    
    if original_query and 'SELECT' in original_query.upper():
        query = original_query.strip()
        if query.endswith(';'):
            query = query[:-1]
        return sqlparse.format(query, strip_comments=True).strip()
    
    raise ValueError("No valid SQL query found in response") 