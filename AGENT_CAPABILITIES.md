# Deep Research Multi-Agent System - Capabilities Overview

## 🎯 What This Agent Can Do

This is a **sophisticated multi-agent research system** that performs deep, comprehensive research on any topic by coordinating multiple specialized AI agents.

## 🏗️ System Architecture

The system uses a **3-stage hierarchical architecture**:

### Stage 1: Research Planning
- **Agent**: Planner (using `moonshotai/Kimi-K2-Thinking`)
- **Function**: Analyzes your research query and generates a detailed research plan
- **Output**: Comprehensive instructions for how to conduct the research

### Stage 2: Task Decomposition
- **Agent**: Task Splitter (using `deepseek-ai/DeepSeek-V3.2-Exp`)
- **Function**: Breaks down the research plan into 3-8 independent, non-overlapping subtasks
- **Output**: Structured JSON list of subtasks, each with:
  - Unique ID
  - Descriptive title
  - Detailed instructions for research

### Stage 3: Parallel Research & Synthesis
- **Coordinator Agent**: Orchestrates the research process (using `MiniMaxAI/MiniMax-M1-80k`)
- **Sub-Agents**: Multiple specialized research agents (using `MiniMaxAI/MiniMax-M1-80k`)
- **Function**: 
  - Coordinator spawns a sub-agent for each subtask
  - Each sub-agent performs deep research using web tools
  - Coordinator synthesizes all findings into a final report

## 🔧 Key Features

### 1. **Web Research Capabilities**
- Uses **Firecrawl MCP (Model Context Protocol)** tools for web scraping and research
- Can access and analyze web content in real-time
- Prioritizes primary and official sources

### 2. **Intelligent Task Distribution**
- Automatically breaks complex research into manageable subtasks
- Each subtask is researched independently by a dedicated agent
- Subtasks are designed to be non-overlapping and comprehensive

### 3. **Structured Output**
- Each sub-agent produces a structured markdown report with:
  - Summary
  - Detailed analysis
  - Key points (bullet points)
  - Sources with citations
- Final report integrates all findings with:
  - Clear structure and headings
  - Integrated analysis
  - Bibliography with deduplicated sources
  - Open questions section

### 4. **Multi-Model Support**
- Uses different specialized models for different stages:
  - Planning: Kimi-K2-Thinking (for strategic thinking)
  - Task splitting: DeepSeek-V3.2-Exp (for structured decomposition)
  - Research execution: MiniMax-M1-80k (for research and synthesis)

## 📋 Research Process Flow

```
User Query
    ↓
[Planner] → Research Plan
    ↓
[Task Splitter] → Subtasks (JSON)
    ↓
[Coordinator] → Spawns Sub-Agents
    ↓
[Sub-Agent 1] → Research Report 1
[Sub-Agent 2] → Research Report 2
[Sub-Agent 3] → Research Report 3
    ...
    ↓
[Coordinator] → Final Synthesized Report
    ↓
research_result.md
```

## 🎨 Example Use Cases

1. **Academic Research**: Deep dive into complex topics with multiple dimensions
2. **Market Analysis**: Research competitors, trends, and market conditions
3. **Historical Analysis**: Multi-faceted historical research with temporal/geographic dimensions
4. **Technical Research**: Comprehensive analysis of technologies, frameworks, or methodologies
5. **Policy Research**: Analysis of policy implications across different dimensions

## 📊 Output Format

The final report includes:
- **Structured sections** with clear headings
- **Integrated findings** from all sub-agents
- **Key drivers and mechanisms** analysis
- **Historical/temporal evolution** when relevant
- **Geographic/thematic patterns** when applicable
- **Open questions** for further research
- **Bibliography** with all sources properly cited

## 🔑 Requirements

- Python 3.11+
- Environment variables:
  - `FIRECRAWL_API_KEY`: For web scraping capabilities
  - `HF_TOKEN`: For Hugging Face model inference
- Dependencies: `smolagents`, `python-dotenv`, and related packages

## 🚀 How to Use

1. Set up environment variables in `.env` file
2. Run: `python main.py`
3. Enter your research query when prompted
4. Wait for the system to:
   - Generate research plan
   - Split into subtasks
   - Execute parallel research
   - Synthesize final report
5. Find results in `research_result.md`

## 💡 Key Advantages

- **Comprehensive**: Covers multiple dimensions of a topic simultaneously
- **Parallel**: Multiple agents work simultaneously on different subtasks
- **Structured**: Produces well-organized, citation-rich reports
- **Adaptive**: Automatically determines how to break down research
- **Source-aware**: Prioritizes quality sources and provides citations

---

*This system demonstrates advanced multi-agent coordination for complex research tasks.*

