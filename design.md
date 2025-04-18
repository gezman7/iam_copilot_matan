# IAM Copilot: Design Document

## Overview

IAM Copilot is an intelligent assistant for Identity and Access Management (IAM) risk management. It provides contextual responses to user queries about IAM security risks in an organization, using a combination of language model technology and database querying capabilities.

This document outlines the architecture, key components, and design decisions for the IAM Copilot system.

## Core Functionality

The IAM Copilot system provides the following core functionality:

1. **Contextual Conversations**: Maintain conversation history to provide coherent, contextual responses across multiple turns
2. **IAM Risk Analysis**: Query and analyze IAM user data to identify security risks and provide recommendations
3. **SQL Query Validation**: Automatically validate and fix SQL queries to prevent errors
4. **Speech-to-Text**: Process voice inputs for hands-free operation
5. **Multi-Interface Support**: Expose functionality through CLI, API, and potential web interfaces

## Architecture

The system follows a layered architecture with clear separation of concerns:

```
┌───────────────────┐
│    Interfaces     │
│  (CLI, API, Web)  │
└────────┬──────────┘
         │
┌────────▼──────────┐
│   Core Services   │
│   (IAM Copilot)   │
└────────┬──────────┘
         │
┌────────▼──────────┐
│  Component Layer  │
│ (Query, Validate) │
└────────┬──────────┘
         │
┌────────▼──────────┐
│   Infrastructure  │
│  (DB, LLM Model)  │
└───────────────────┘
```

### Key Components

#### 1. IAM Copilot Core

The central component that coordinates all functionality, implemented in `core/copilot.py`. It:

- Maintains conversation state using LangGraph
- Routes queries to appropriate processors
- Manages thread-based conversation history
- Applies appropriate guidelines based on risk category

#### 2. Query Agent

Handles the processing of user queries, implemented in `core/query_agent.py`. It:

- Converts natural language queries to SQL
- Executes validated SQL against the database
- Handles errors and provides corrections

#### 3. SQL Validator

Validates and fixes SQL queries, implemented in `services/sql_validator.py`. It:

- Parses SQL queries for syntax errors
- Validates table and column references
- Attempts to fix common SQL errors automatically
- Provides specific error messages for unfixable issues

#### 4. Speech Transcriber

Handles voice input processing, implemented in `speech/transcriber.py`. It:

- Converts audio files to text
- Supports real-time microphone input
- Handles various audio formats

#### 5. State Management

Manages conversation state, implemented in `models/state.py`. It:

- Tracks messages in conversation history
- Preserves thread identity across interactions
- Maintains error state when needed

## Workflow

### Basic Query Flow

1. User sends a query through one of the interfaces (CLI, API)
2. IAM Copilot:
   - Creates or retrieves conversation thread
   - Processes query through LangGraph workflow
3. Query Agent:
   - Translates query to SQL with LLM
   - Validates SQL with SQL Validator
   - Executes validated query against database
4. Response Generator:
   - Identifies risk type in query/results
   - Applies appropriate guidelines
   - Generates contextual response
5. Interface:
   - Displays formatted response to user

### Speech Input Flow

1. User provides audio input
2. Speech Transcriber:
   - Processes audio file or stream
   - Converts to text
3. Standard query flow proceeds with the transcribed text

### SQL Validation Flow

1. Query Agent generates SQL from natural language
2. SQL Validator:
   - Checks syntax using SQLGlot
   - Validates tables and columns
   - Attempts correction if needed
3. If validation successful:
   - Query is executed
4. If validation fails but correction successful:
   - Corrected query is executed
5. If correction fails:
   - Error is returned to user with suggestion

## Error Handling

The system implements robust error handling at multiple levels:

1. **Input Validation**: All user inputs are validated before processing
2. **SQL Validation**: SQL queries are validated and fixed when possible
3. **Graceful Degradation**: System provides helpful responses even when it cannot fully answer a query
4. **Detailed Logging**: Comprehensive logging for debugging and monitoring
5. **User-Friendly Errors**: Error messages are translated into user-friendly terms

## Security Considerations

1. **Database Access**: Read-only access to the database
2. **Input Sanitization**: All user inputs are sanitized before processing
3. **API Authentication**: API endpoints require authentication (implementation-dependent)
4. **Data Privacy**: Guidelines for handling sensitive IAM data

## Extensibility

The system is designed to be extensible:

1. **Modular Architecture**: Clear separation of concerns allows replacing components
2. **Pluggable LLM**: Support for different LLM backends
3. **Multiple Interfaces**: Easy to add new interfaces (web, mobile, etc.)
4. **Customizable Guidelines**: Guidelines can be updated without code changes

## Future Enhancements

1. **Automated Risk Remediation**: Suggest and potentially implement fixes for identified risks
2. **Dashboard Integration**: Integrate with IAM dashboards for visual representation
3. **Scheduled Scanning**: Regular automated scans for IAM risks
4. **Multi-DB Support**: Support for various database types beyond SQLite
5. **Cloud Provider Integration**: Direct integration with major cloud IAM services

## Conclusion

IAM Copilot combines AI language capabilities with IAM security expertise to create an intelligent assistant for IAM risk management. Its modular design allows for extensibility, while its focus on user experience makes it accessible to both security experts and general users. 