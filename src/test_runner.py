import json
import os
import argparse
import pandas as pd
from tabulate import tabulate
from query_writer import QueryWriter
from langchain_core.messages import AIMessage


class TestRunner:
    def __init__(self, db, test_data_path="test_data/test_cases.json"):
        """Initialize the TestRunner with database and test data."""
        self.db = db
        self.test_data_path = test_data_path
        self.query_writer = QueryWriter(db)
        self.results = []
        
    def load_test_cases(self):
        """Load test cases from the JSON file."""
        if not os.path.exists(self.test_data_path):
            raise FileNotFoundError(f"Test data file not found: {self.test_data_path}")
            
        with open(self.test_data_path, 'r') as f:
            data = json.load(f)
            
        return data.get('test_cases', [])
        
    def run_test_cases(self, verbose=False):
        """Run all test cases and collect results."""
        test_cases = self.load_test_cases()
        print(f"Loaded {len(test_cases)} test cases.")
        
        for test_case in test_cases:
            result = self.run_single_test(test_case, verbose)
            self.results.append(result)
            
        return self.results
        
    def run_single_test(self, test_case, verbose=False):
        """Run a single test case and return the result."""
        test_id = test_case.get('id', 'unknown')
        description = test_case.get('description', '')
        user_query = test_case.get('user_query', '')
        expected_sql = test_case.get('expected_sql', '')
        expected_result = test_case.get('expected_result', [])
        
        if verbose:
            print(f"\nRunning test: {test_id} - {description}")
            print(f"User query: {user_query}")
            print(f"Expected SQL: {expected_sql}")
        
        # Reset conversation history for each test
        self.query_writer.conversation_history = []
        
        # Process the query
        response = self.query_writer.process_query(user_query)
        actual_sql = response.content if isinstance(response, AIMessage) else str(response)
        
        # Compare SQL queries (ignoring case and whitespace)
        sql_match = self._compare_sql(expected_sql, actual_sql)
        
        # Run the actual SQL to get results (if possible)
        try:
            actual_result = self.db.run(actual_sql)
            result_match = self._compare_results(expected_result, actual_result)
        except Exception as e:
            actual_result = f"Error: {str(e)}"
            result_match = False
        
        result = {
            'test_id': test_id,
            'description': description,
            'user_query': user_query,
            'expected_sql': expected_sql,
            'actual_sql': actual_sql,
            'sql_match': sql_match,
            'expected_result': expected_result,
            'actual_result': actual_result,
            'result_match': result_match,
            'passed': sql_match and result_match
        }
        
        if verbose:
            print(f"Actual SQL: {actual_sql}")
            print(f"SQL Match: {'✅' if sql_match else '❌'}")
            print(f"Result Match: {'✅' if result_match else '❌'}")
            print(f"Test Passed: {'✅' if result_match and sql_match else '❌'}")
            
        return result
        
    def _compare_sql(self, expected_sql, actual_sql):
        """Compare SQL queries, ignoring case and whitespace differences."""
        # Normalize SQL by removing extra whitespace and converting to lowercase
        def normalize_sql(sql):
            # Remove comments
            lines = sql.split('\n')
            lines = [line for line in lines if not line.strip().startswith('--')]
            sql = ' '.join(lines)
            
            # Replace multiple whitespaces with a single space
            import re
            sql = re.sub(r'\s+', ' ', sql).strip()
            
            # Remove semicolon at the end if present
            if sql.endswith(';'):
                sql = sql[:-1]
                
            return sql.lower()
        
        return normalize_sql(expected_sql) == normalize_sql(actual_sql)
        
    def _compare_results(self, expected_result, actual_result):
        """Compare query results, handling different result formats."""
        # Simple comparison for now, can be enhanced later
        if not expected_result:
            return True
            
        # Convert actual result to a consistent format if needed
        if isinstance(actual_result, list) and actual_result and isinstance(actual_result[0], tuple):
            # Convert tuple results to dicts for comparison
            columns = list(expected_result[0].keys())
            actual_dicts = []
            for row in actual_result:
                actual_dict = {}
                for i, col in enumerate(columns):
                    if i < len(row):
                        actual_dict[col] = row[i]
                actual_dicts.append(actual_dict)
            actual_result = actual_dicts
            
        # Compare lengths first
        if len(expected_result) != len(actual_result):
            return False
            
        # Compare contents
        try:
            for i, expected_row in enumerate(expected_result):
                actual_row = actual_result[i]
                if isinstance(expected_row, dict) and isinstance(actual_row, dict):
                    # Compare dictionaries
                    if not all(actual_row.get(k) == v for k, v in expected_row.items()):
                        return False
                else:
                    # Direct comparison
                    if expected_row != actual_row:
                        return False
            return True
        except (IndexError, AttributeError, TypeError):
            return False
            
    def generate_report(self, output_format='text', output_file=None):
        """Generate a report of test results."""
        if not self.results:
            print("No test results to report.")
            return
            
        # Calculate summary statistics
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['passed'])
        sql_match_count = sum(1 for r in self.results if r['sql_match'])
        result_match_count = sum(1 for r in self.results if r['result_match'])
        
        summary = {
            'Total Tests': total_tests,
            'Passed Tests': passed_tests,
            'Pass Rate': f"{(passed_tests / total_tests) * 100:.2f}%",
            'SQL Match Rate': f"{(sql_match_count / total_tests) * 100:.2f}%",
            'Result Match Rate': f"{(result_match_count / total_tests) * 100:.2f}%"
        }
        
        # Create detailed results table
        details = []
        for r in self.results:
            details.append({
                'Test ID': r['test_id'],
                'Description': r['description'],
                'SQL Match': '✅' if r['sql_match'] else '❌',
                'Result Match': '✅' if r['result_match'] else '❌',
                'Passed': '✅' if r['passed'] else '❌'
            })
            
        # Output in requested format
        if output_format == 'text':
            report = self._text_report(summary, details)
        elif output_format == 'csv':
            report = self._csv_report(summary, details, output_file)
        elif output_format == 'json':
            report = self._json_report(summary, details, output_file)
        elif output_format == 'html':
            report = self._html_report(summary, details, output_file)
        else:
            report = "Unsupported output format."
            
        if output_file and output_format != 'text':
            print(f"Report saved to {output_file}")
        else:
            print(report)
            
        return report
        
    def _text_report(self, summary, details):
        """Generate a text report."""
        report = "=== Query Writer Test Results ===\n\n"
        
        # Summary section
        report += "Summary:\n"
        for key, value in summary.items():
            report += f"{key}: {value}\n"
        
        # Details section
        report += "\nDetailed Results:\n"
        report += tabulate(details, headers="keys", tablefmt="grid")
        
        return report
        
    def _csv_report(self, summary, details, output_file):
        """Generate a CSV report."""
        # Summary dataframe
        summary_df = pd.DataFrame([summary])
        
        # Details dataframe
        details_df = pd.DataFrame(details)
        
        # Save to CSV
        if output_file:
            summary_df.to_csv(f"{output_file}_summary.csv", index=False)
            details_df.to_csv(f"{output_file}_details.csv", index=False)
            
        return "CSV report generated."
        
    def _json_report(self, summary, details, output_file):
        """Generate a JSON report."""
        report_data = {
            'summary': summary,
            'details': details,
            'raw_results': self.results
        }
        
        if output_file:
            with open(f"{output_file}.json", 'w') as f:
                json.dump(report_data, f, indent=2)
                
        return "JSON report generated."
        
    def _html_report(self, summary, details, output_file):
        """Generate an HTML report."""
        # Convert to dataframes
        summary_df = pd.DataFrame([summary])
        details_df = pd.DataFrame(details)
        
        # Generate HTML
        html = "<html><head><title>Query Writer Test Results</title>"
        html += "<style>body{font-family:Arial,sans-serif;margin:20px;} "
        html += "table{border-collapse:collapse;width:100%;margin-bottom:20px;} "
        html += "th,td{text-align:left;padding:8px;border:1px solid #ddd;} "
        html += "th{background-color:#f2f2f2;} "
        html += "tr:nth-child(even){background-color:#f9f9f9;} "
        html += "h1,h2{color:#333;}</style></head><body>"
        html += "<h1>Query Writer Test Results</h1>"
        
        html += "<h2>Summary</h2>"
        html += summary_df.to_html(index=False)
        
        html += "<h2>Detailed Results</h2>"
        html += details_df.to_html(index=False)
        
        html += "</body></html>"
        
        if output_file:
            with open(f"{output_file}.html", 'w') as f:
                f.write(html)
                
        return "HTML report generated."


def main():
    """Main function to run the test suite from command line."""
    parser = argparse.ArgumentParser(description='Run tests for the Query Writer system.')
    parser.add_argument('--test-data', dest='test_data_path', default='test_data/test_cases.json',
                        help='Path to the test data JSON file')
    parser.add_argument('--verbose', action='store_true', 
                        help='Enable verbose output')
    parser.add_argument('--format', choices=['text', 'csv', 'json', 'html'], default='text',
                        help='Output format for the test report')
    parser.add_argument('--output', dest='output_file',
                        help='Output file path (without extension)')
    
    args = parser.parse_args()
    
    # Here you would normally connect to your database
    # This is a placeholder - replace with your actual DB connection
    from loader import create_test_db
    db = create_test_db()
    
    # Run tests
    runner = TestRunner(db, args.test_data_path)
    runner.run_test_cases(args.verbose)
    runner.generate_report(args.format, args.output_file)


if __name__ == "__main__":
    main() 