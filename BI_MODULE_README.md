# Business Intelligence Module - 6_business_intelligence.py

## Overview

This module implements a GraphRAG-based Business Intelligence Engine that handles 6 types of complex business queries:

1. **COUNTING** - "How many Python developers are available?"
2. **FILTERING** - "Find developers with React experience"
3. **AGGREGATION** - "What is the average experience for ML projects?"
4. **REASONING** - "Show me developers who worked together"
5. **TEMPORAL** - "Who becomes available after their current project ends?"
6. **SCENARIO** - "What's the optimal team composition for an upcoming project?"

## Architecture

### Components

```
BusinessIntelligenceEngine
├── classify_query() - Uses LLM to determine query type
├── handle_counting_query() - Count entities
├── handle_filtering_query() - Filter by criteria
├── handle_aggregation_query() - Calculate aggregates
├── handle_reasoning_query() - Multi-hop relationships
├── handle_temporal_query() - Time-based queries
├── handle_scenario_query() - Complex business logic
├── answer_question() - Main entry point
└── format_result() - Format results for display
```

## Usage

### Basic Usage

```python
from langchain_6_business_intelligence import BusinessIntelligenceEngine

engine = BusinessIntelligenceEngine()

# Ask a question
result = engine.answer_question("How many Python developers are available?")

# Format and display
print(engine.format_result(result))
```

### Query Examples

**Counting Queries**

```python
engine.answer_question("How many Python developers are available?")
engine.answer_question("Count developers with AWS certifications")
```

**Filtering Queries**

```python
engine.answer_question("Find developers with React experience")
engine.answer_question("List available developers")
```

**Aggregation Queries**

```python
engine.answer_question("What is the average experience for all developers?")
engine.answer_question("Total capacity available for Q4 projects")
```

**Reasoning Queries**

```python
engine.answer_question("Show me developers who worked together")
engine.answer_question("Developers from same university")
```

**Temporal Queries**

```python
engine.answer_question("Who becomes available after their current project ends?")
engine.answer_question("Developers finishing projects in next 30 days")
```

**Scenario Queries**

```python
engine.answer_question("What's the optimal team composition for an upcoming project?")
engine.answer_question("Skills gaps analysis for upcoming projects")
engine.answer_question("Risk assessment: identify critical skills")
```

## How It Works

### 1. Query Classification (LLM-based)

The engine uses Azure OpenAI to classify incoming questions into one of 6 types.

### 2. Query Handler Selection

Based on classification, the appropriate handler is selected.

### 3. Cypher Query Generation

Each handler builds a Cypher query optimized for Neo4j execution.

### 4. Result Formatting

Results are formatted for human-readable display.

## Response Format

```json
{
  "type": "counting",
  "query": "How many Python developers are available?",
  "result": 14,
  "explanation": "Found 14 matching items for: How many Python developers are available?",
  "cypher": "MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)...",
  "success": true
}
```

## Supported Neo4j Entities

### Nodes

- **Person** - Developers
- **Skill** - Technical skills
- **Project** - Projects/RFPs
- **Company** - Companies
- **Location** - Locations
- **University** - Universities

### Relationships

- `HAS_SKILL` - Person has skill
- `WORKED_AT` - Person worked at company
- `ASSIGNED_TO` - Person assigned to project
- `LOCATED_IN` - Person/Company located in location
- `STUDIED_AT` - Person studied at university

## Performance Considerations

- Counting queries: < 100ms
- Filtering queries: < 500ms (depends on result set size)
- Aggregation queries: < 200ms
- Reasoning queries: < 1s (multi-hop traversal)
- Temporal queries: < 300ms
- Scenario queries: < 2s (complex logic)

## Integration with Chatbot

This module is designed to be easily integrated with:

- Streamlit chatbot UI (see `7_chatbot_streamlit.py`)
- FastAPI REST API
- LangGraph agent orchestration
- Chat history and context management

## Future Enhancements

1. **Natural Language to Cypher Translation** - Use LLM to generate custom Cypher for any query
2. **Query Caching** - Cache frequently asked questions
3. **Query Optimization** - Analyze query plans and optimize execution
4. **Multi-step Queries** - Handle "follow-up" questions with context
5. **Custom Query Templates** - Allow users to define custom query patterns
6. **Analytics Dashboard** - Visualize query results with charts/graphs

## Testing

Run the module directly to test all query types:

```bash
python3 6_business_intelligence.py
```

This will execute 6 test queries (one for each type) and display results.
