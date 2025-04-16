import logging
import json
import os
import sqlite3
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

from src.Iam_copilot import IAMCopilot

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"llm_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("talk_fetch_db")

class LLMValidationTest:
    """Test suite for validating LLM responses against actual database data"""
    
    def __init__(self, db_path="iam_risks.db"):
        self.db_path = db_path
        
        # Initialize the agent
        logger.info(f"Initializing SearchDetectionSnapshot with database: {db_path}")
        self.search_agent = IAMCopilot(db_path=db_path)
        
        # Connect directly to the database for validation
        self.db_conn = sqlite3.connect(db_path)
        self.db_conn.row_factory = sqlite3.Row
        
        # Test cases - each with a query and validation logic
        self.test_cases = [
            {
                "name": "inactive_users_count",
                "query": "How many inactive users do we have?",
                "expected_data": self._get_inactive_users_count,
                "validation_type": "numeric_match"
            },
            {
                "name": "weak_mfa_users",
                "query": "Show me users with weak MFA configurations",
                "expected_data": self._get_weak_mfa_users,
                "validation_type": "list_verification"
            },
            {
                "name": "service_accounts_summary",
                "query": "Summarize our service account risks",
                "expected_data": self._get_service_account_summary,
                "validation_type": "contains_values"
            },
            {
                "name": "never_logged_in",
                "query": "How many users have never logged in?",
                "expected_data": self._get_never_logged_in_count,
                "validation_type": "numeric_match"
            },
            {
                "name": "risk_distribution",
                "query": "What's the distribution of risk types in our environment?",
                "expected_data": self._get_risk_distribution,
                "validation_type": "distribution_check"
            }
        ]
        
        # Track extracted SQL queries
        self.extracted_queries = {}
        
    def _get_inactive_users_count(self) -> int:
        """Get actual count of inactive users from database"""
        cursor = self.db_conn.cursor()
        result = cursor.execute(
            "SELECT COUNT(*) FROM UserRiskTypes WHERE risk_topic = 'INACTIVE_USERS'"
        ).fetchone()
        return result[0] if result else 0
    
    def _get_weak_mfa_users(self) -> List[str]:
        """Get list of users with weak MFA"""
        cursor = self.db_conn.cursor()
        result = cursor.execute(
            "SELECT UserID FROM UserRiskTypes WHERE risk_topic = 'WEAK_MFA_USERS' LIMIT 100"
        ).fetchall()
        return [row['UserID'] for row in result] if result else []
    
    def _get_service_account_summary(self) -> Dict[str, Any]:
        """Get summary of service account risks"""
        cursor = self.db_conn.cursor()
        count = cursor.execute(
            "SELECT COUNT(*) FROM UserRiskTypes WHERE risk_topic = 'SERVICE_ACCOUNTS'"
        ).fetchone()
        
        # Join with Users table to get additional information if needed
        # This is a simplified example as we don't have risk_level field
        service_account_count = count[0] if count else 0
        
        return {
            "total_count": service_account_count
        }
    
    def _get_never_logged_in_count(self) -> int:
        """Get count of users who have never logged in"""
        cursor = self.db_conn.cursor()
        result = cursor.execute(
            "SELECT COUNT(*) FROM UserRiskTypes WHERE risk_topic = 'NEVER_LOGGED_IN_USERS'"
        ).fetchone()
        return result[0] if result else 0
    
    def _get_risk_distribution(self) -> Dict[str, int]:
        """Get distribution of risk types"""
        cursor = self.db_conn.cursor()
        result = cursor.execute(
            "SELECT risk_topic, COUNT(*) as count FROM UserRiskTypes GROUP BY risk_topic"
        ).fetchall()
        
        return {row['risk_topic']: row['count'] for row in result} if result else {}
    
    def _extract_sql_query(self, trajectory: List[str]) -> Optional[str]:
        """Extract SQL query from agent trajectory"""
        for message in trajectory:
            # Look for db_query_tool calls
            match = re.search(r"db_query_tool\(['\"](.+?)['\"]\)", message)
            if match:
                return match.group(1)
            
            # Alternative pattern - look for SQL statements
            query_match = re.search(r"SELECT.+?FROM.+?(WHERE.+?)?", message, re.IGNORECASE | re.DOTALL)
            if query_match:
                return query_match.group(0)
        
        return None
    
    def validate_numeric_match(self, llm_response: str, expected_value: int) -> bool:
        """Validate if LLM response contains the correct numeric value"""
        # Extract numbers from response
        numbers = re.findall(r'\b\d+\b', llm_response)
        
        # Convert to integers
        integers = [int(num) for num in numbers]
        
        # Check if the expected value is in the extracted numbers
        return expected_value in integers
    
    def validate_list_verification(self, llm_response: str, expected_list: List[str]) -> Dict[str, Any]:
        """Validate if LLM response contains correct list items"""
        if not expected_list:
            return {"valid": False, "reason": "Expected list is empty"}
        
        # Count how many items from the expected list appear in the response
        found_items = [item for item in expected_list if item in llm_response]
        
        # Calculate match percentage
        match_percentage = (len(found_items) / len(expected_list)) * 100 if expected_list else 0
        
        return {
            "valid": match_percentage > 0,  # At least some matches
            "match_percentage": match_percentage,
            "found_count": len(found_items),
            "expected_count": len(expected_list)
        }
    
    def validate_contains_values(self, llm_response: str, expected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate if LLM response contains expected values"""
        results = {}
        
        for key, value in expected_data.items():
            # Convert value to string for searching
            str_value = str(value)
            
            # Check if value is in the response
            results[key] = str_value in llm_response
        
        # Valid if at least half of the values are found
        valid_count = sum(1 for v in results.values() if v)
        results["valid"] = valid_count >= len(results) / 2
        
        return results
    
    def validate_distribution_check(self, llm_response: str, expected_distribution: Dict[str, int]) -> Dict[str, Any]:
        """Validate if LLM response correctly represents the distribution of values"""
        if not expected_distribution:
            return {"valid": False, "reason": "Expected distribution is empty"}
        
        # Check if risk topics are mentioned
        risk_topic_matches = {}
        
        for risk_topic in expected_distribution.keys():
            risk_topic_matches[risk_topic] = risk_topic in llm_response
        
        # Check if the relative proportions are correct
        # This is a simplistic check - we're just seeing if larger categories are presented as larger
        mentioned_correct_proportion = True
        sorted_risks = sorted(expected_distribution.items(), key=lambda x: x[1], reverse=True)
        
        # No need to check proportions if all values are equal or we have just one value
        if len(sorted_risks) > 1 and sorted_risks[0][1] != sorted_risks[-1][1]:
            # Check if the response mentions the largest risk type is the largest
            largest_risk = sorted_risks[0][0]
            if "largest" in llm_response.lower() or "most" in llm_response.lower():
                mentioned_correct_proportion = largest_risk in llm_response
        
        return {
            "valid": any(risk_topic_matches.values()),
            "risk_topic_matches": risk_topic_matches,
            "mentioned_correct_proportion": mentioned_correct_proportion
        }
    
    def run_tests(self) -> Dict[str, Any]:
        """Run all tests and return results"""
        results = {}
        
        for test_case in self.test_cases:
            test_name = test_case["name"]
            query = test_case["query"]
            validation_type = test_case["validation_type"]
            
            logger.info(f"Running test: {test_name}")
            logger.info(f"Query: {query}")
            
            # Get expected data
            expected_data = test_case["expected_data"]()
            logger.info(f"Expected data: {expected_data}")
            
            # Run query through SearchDetectionSnapshot
            agent_result = self.search_agent.process_speech_query(query)
            
            # Log the full trajectory for debugging
            logger.debug(f"Agent trajectory: {json.dumps(agent_result.get('trajectory', []), indent=2)}")
            
            # Extract SQL query from trajectory
            extracted_query = self._extract_sql_query(agent_result.get('trajectory', []))
            if extracted_query:
                self.extracted_queries[test_name] = extracted_query
                logger.info(f"Extracted SQL query: {extracted_query}")
            else:
                logger.warning(f"Could not extract SQL query for test: {test_name}")
            
            # Get LLM response
            llm_response = agent_result.get('response', '')
            logger.info(f"LLM response: {llm_response}")
            
            # Validate response based on validation type
            validation_result = None
            
            if validation_type == "numeric_match":
                validation_result = self.validate_numeric_match(llm_response, expected_data)
            elif validation_type == "list_verification":
                validation_result = self.validate_list_verification(llm_response, expected_data)
            elif validation_type == "contains_values":
                validation_result = self.validate_contains_values(llm_response, expected_data)
            elif validation_type == "distribution_check":
                validation_result = self.validate_distribution_check(llm_response, expected_data)
            
            # Log validation result
            logger.info(f"Validation result: {validation_result}")
            
            # Store results
            results[test_name] = {
                "query": query,
                "expected_data": expected_data,
                "llm_response": llm_response,
                "extracted_query": extracted_query,
                "validation_result": validation_result
            }
            
            logger.info(f"Test {test_name} completed")
            logger.info("-" * 50)
        
        return results
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate a report from test results"""
        valid_tests = sum(1 for test_name, test_data in results.items() 
                         if test_data.get('validation_result') and 
                         (isinstance(test_data['validation_result'], bool) and test_data['validation_result'] or
                          isinstance(test_data['validation_result'], dict) and test_data['validation_result'].get('valid')))
                          
        total_tests = len(results)
        
        report = []
        report.append(f"LLM Validation Test Report")
        report.append(f"========================")
        report.append(f"Tests run: {total_tests}")
        report.append(f"Tests passed: {valid_tests}")
        report.append(f"Success rate: {valid_tests/total_tests*100:.1f}%")
        report.append("")
        
        report.append("Test Results Summary:")
        report.append("--------------------")
        
        for test_name, test_data in results.items():
            validation_result = test_data.get('validation_result')
            is_valid = False
            
            if isinstance(validation_result, bool):
                is_valid = validation_result
            elif isinstance(validation_result, dict):
                is_valid = validation_result.get('valid', False)
            
            status = "PASS" if is_valid else "FAIL"
            report.append(f"{test_name}: {status}")
            
            # Add extracted SQL query if available
            if test_data.get('extracted_query'):
                report.append(f"  Query: {test_data['extracted_query']}")
            
            # Add validation details
            if isinstance(validation_result, dict):
                for key, value in validation_result.items():
                    if key != 'valid':
                        report.append(f"  {key}: {value}")
            
            report.append("")
        
        report.append("Hallucination Analysis:")
        report.append("---------------------")
        
        # Analyze potential hallucinations
        hallucinations = []
        
        for test_name, test_data in results.items():
            validation_result = test_data.get('validation_result')
            is_valid = False
            
            if isinstance(validation_result, bool):
                is_valid = validation_result
            elif isinstance(validation_result, dict):
                is_valid = validation_result.get('valid', False)
            
            if not is_valid:
                hallucinations.append({
                    "test_name": test_name,
                    "expected": test_data.get('expected_data'),
                    "response": test_data.get('llm_response')
                })
        
        if hallucinations:
            report.append(f"Potential hallucinations detected in {len(hallucinations)} tests:")
            
            for h in hallucinations:
                report.append(f"  - {h['test_name']}:")
                report.append(f"    Expected: {h['expected']}")
                report.append(f"    Response excerpt: {h['response'][:150]}...")
                report.append("")
        else:
            report.append("No clear hallucinations detected.")
        
        report.append("")
        report.append("Recommendations:")
        report.append("---------------")
        
        if valid_tests < total_tests:
            report.append("1. Review and improve SQL query generation for failed tests")
            report.append("2. Consider adding more structure to the agent's responses to make numerical data more consistent")
            report.append("3. Enhance the agent's ability to verify data before responding")
        else:
            report.append("The LLM is performing well for the tested queries.")
        
        return "\n".join(report)

    def close(self):
        """Close database connection"""
        if self.db_conn:
            self.db_conn.close()


if __name__ == "__main__":
    try:
        # Run tests
        validator = LLMValidationTest()
        results = validator.run_tests()
        
        # Generate and log report
        report = validator.generate_report(results)
        logger.info(f"\n{report}")
        
        # Print report to console
        print("\n" + report)
        
        # Clean up
        validator.close()
        
    except Exception as e:
        logger.error(f"Error running validation tests: {e}", exc_info=True)
        print(f"Error: {e}") 