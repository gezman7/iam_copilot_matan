#!/usr/bin/env python3

import re
import logging
from typing import List, Tuple, Optional

from langchain_core.messages import AnyMessage, HumanMessage, AIMessage

def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate a simple similarity score between two texts.
    
    This is a basic implementation - in a production environment, 
    you would use an embedding model for better similarity matching.
    
    Args:
        text1: First text string
        text2: Second text string
        
    Returns:
        Similarity score between 0.0 and 1.0
    """
    # Convert to lowercase and remove punctuation
    text1 = re.sub(r'[^\w\s]', '', text1.lower())
    text2 = re.sub(r'[^\w\s]', '', text2.lower())
    
    # Split into words
    words1 = set(text1.split())
    words2 = set(text2.split())
    
    # Calculate Jaccard similarity
    if not words1 or not words2:
        return 0.0
        
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    return intersection / union if union > 0 else 0.0

def find_risk_type(
    user_query: str, 
    messages: List[AnyMessage], 
    risk_categories: List[str],
    logger: Optional[logging.Logger] = None,
    debug: bool = False
) -> Tuple[str, bool]:
    """Find the most similar risk type based on user query and conversation history.
    
    Args:
        user_query: The user's question
        messages: List of conversation messages
        risk_categories: List of risk category strings to match against
        logger: Optional logger for debug information
        debug: Whether to log debug information
        
    Returns:
        Tuple of (risk_type, is_general_guideline)
    """
    if not user_query:
        return "GENERAL", True
        
    # Extract conversation history text
    conversation_text = ""
    if messages:
        for msg in messages:
            if isinstance(msg, (HumanMessage, AIMessage)):
                content = getattr(msg, "content", "")
                if content:
                    conversation_text += f" {content}"
    
    # Combine user query and conversation history
    combined_text = f"{user_query} {conversation_text}"
    
    # If no exact match, use similarity search
    best_score = 0.0
    best_risk_type = "GENERAL"
    
    for risk_type in risk_categories:
        # Calculate similarity
        similarity = calculate_similarity(combined_text, risk_type.replace("_", " "))
        
        if similarity > best_score:
            best_score = similarity
            best_risk_type = risk_type
    
    # Use threshold to determine if we should return general guidelines
    if best_score < 0.1:  # Threshold can be adjusted
        if debug and logger:
            logger.debug(f"No significant match found, using general guidelines. Best score: {best_score}")
        return "GENERAL", True
        
    if debug and logger:
        logger.debug(f"Best risk type match: {best_risk_type} with score {best_score}")
        
    return best_risk_type, False

def has_user_data(query_result: str) -> bool:
    """Check if the query result contains user data.
    
    Args:
        query_result: SQL query result string
        
    Returns:
        True if user data is detected, False otherwise
    """
    if not query_result:
        return False
        
    # Look for patterns that indicate user data
    user_data_patterns = [
        r"user_id",
        r"username",
        r"email",
        r"name",
        r"\|\s*\d+\s*\|",  # Matches pipe-delimited data with numbers
        r"row\(s\) returned"
    ]
    
    # Check if the result is empty or indicates no data
    empty_result_patterns = [
        r"no rows",
        r"0 row\(s\) returned",
        r"no results",
        r"empty result",
        r"no data"
    ]
    
    # Check for empty result patterns
    for pattern in empty_result_patterns:
        if re.search(pattern, query_result, re.IGNORECASE):
            return False
            
    # Check for user data patterns
    for pattern in user_data_patterns:
        if re.search(pattern, query_result, re.IGNORECASE):
            return True
            
    # Default to assuming there is data if we can't determine otherwise
    # Check if result has substantial content
    return len(query_result.strip()) > 20 