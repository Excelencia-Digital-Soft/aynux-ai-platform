# LangSmith Tracing Troubleshooting Guide

## Overview

This guide provides comprehensive instructions for debugging and troubleshooting LangSmith tracing in the Aynux LangGraph multi-agent system.

## ✅ Quick Verification

### 1. Run the verification script:
```bash
uv run python test_langsmith_final_verification.py
```

### 2. Check LangSmith UI:
- Navigate to: https://smith.langchain.com/
- Select project: `pr-vacant-technician-19`
- Look for recent traces

## 🔧 Common Issues & Solutions

### Issue 1: "No traces appearing in LangSmith UI"

**Symptoms:**
- Code runs without errors
- No traces visible in LangSmith dashboard

**Solutions:**
1. **Check API key permissions:**
   ```bash
   # Verify API key is set
   echo $LANGSMITH_API_KEY
   ```

2. **Wait for processing (2-5 minutes)**
   - LangSmith has processing delays
   - Try refreshing the UI

3. **Verify internet connectivity:**
   ```bash
   # Test connectivity
   uv run python -c "from langsmith import Client; print('OK' if Client().list_projects(limit=1) else 'FAILED')"
   ```

4. **Check project name:**
   - Ensure `LANGSMITH_PROJECT` matches your LangSmith project
   - Default: `pr-vacant-technician-19`

### Issue 2: "run_type validation errors"

**Symptoms:**
```
HTTPError('422 Client Error: unknown for url: https://api.smith.langchain.com/runs/multipart'
schema validation failed: run_type must be one of: "tool", "chain", "llm", "retriever", "embedding", "prompt", "parser"
```

**Solution:** ✅ **FIXED**
- Updated `app/agents/routing/graph_router.py`
- Changed `run_type="routing"` to `run_type="chain"`

### Issue 3: "Environment variables not loading"

**Symptoms:**
```
LANGSMITH_TRACING: Not set
LANGSMITH_API_KEY: Not set
```

**Solution:**
- Always use `uv run` to ensure `.env` file loading:
  ```bash
  # Correct
  uv run python your_script.py
  
  # Incorrect (may not load .env)
  python your_script.py
  ```

### Issue 4: "Supervisor agent method signature error"

**Symptoms:**
```
SupervisorAgent._evaluate_response_quality() got an unexpected keyword argument 'conversation_context'
```

**Solution:** ✅ **FIXED**
- Updated `app/agents/subagent/supervisor_agent.py`
- Fixed method signature to accept `conversation_context` parameter

### Issue 5: "Module import errors"

**Symptoms:**
```
No module named 'pydantic_settings'
No module named 'app.services.chat_service'
```

**Solution:**
1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Use correct service imports:**
   ```python
   # Correct
   from app.services.langgraph_chatbot_service import LangGraphChatbotService
   
   # Incorrect
   from app.services.chat_service import ChatService
   ```

## 🚀 Production Usage

### 1. Enable tracing in production:
```bash
# .env file
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_api_key
LANGSMITH_PROJECT=your_project_name
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

### 2. Verify configuration:
```python
from app.config.langsmith_init import get_langsmith_status
status = get_langsmith_status()
print(f"Tracing enabled: {status['tracing_enabled']}")
```

### 3. Run conversation test:
```bash
uv run python test_real_conversation_tracing.py
```

## 📊 Monitoring & Analysis

### What to look for in LangSmith UI:

1. **Main conversation traces:**
   - Name: `graph_invoke` or `conversation_*`
   - Contains full conversation flow

2. **Agent execution traces:**
   - Names: `orchestrator_agent_process`, `product_agent_process`, etc.
   - Shows individual agent processing

3. **Integration calls:**
   - Names: `postgresql_*`, `ollama_*`, `chromadb_*`
   - External service interactions

4. **Router decisions:**
   - Names: `route_to_agent`, `supervisor_should_continue`
   - Agent routing logic

### Key metrics to monitor:
- **Latency**: Response times for each agent
- **Error rates**: Failed traces or exceptions
- **Token usage**: LLM token consumption
- **Success rates**: Completed vs. failed conversations

## 🔍 Debugging Tools

### 1. Connectivity test:
```bash
uv run python test_langsmith_connectivity.py
```

### 2. Full integration test:
```bash
uv run python test_langsmith_full_integration.py
```

### 3. Real conversation test:
```bash
uv run python test_real_conversation_tracing.py
```

### 4. Final verification:
```bash
uv run python test_langsmith_final_verification.py
```

## 🛠️ Advanced Configuration

### Custom trace metadata:
```python
from app.agents.utils.tracing import trace_async_method

@trace_async_method(
    name="custom_operation",
    run_type="chain",
    metadata={
        "operation_type": "custom",
        "version": "1.0",
        "environment": "production"
    }
)
async def custom_function():
    # Your code here
    pass
```

### Conversation tracking:
```python
from app.config.langsmith_config import ConversationTracer

conv_tracer = ConversationTracer("conv_123", "user_456")
conv_tracer.add_message("user", "Hello")
conv_tracer.add_agent_transition("orchestrator", "product", "Product inquiry")
conv_tracer.end_conversation("success")
```

## 📋 Verification Checklist

- [ ] ✅ LangSmith API key configured and valid
- [ ] ✅ Project name matches LangSmith dashboard
- [ ] ✅ Environment variables loading with `uv run`
- [ ] ✅ No run_type validation errors
- [ ] ✅ Supervisor agent method signature fixed
- [ ] ✅ All test scripts passing
- [ ] ✅ Traces appearing in LangSmith UI
- [ ] ✅ Proper trace hierarchy visible
- [ ] ✅ Agent metadata and performance metrics available

## 📞 Support

If issues persist after following this guide:

1. **Check LangSmith service status:** https://status.langchain.com/
2. **Verify API key permissions** in LangSmith dashboard
3. **Review LangSmith documentation:** https://docs.smith.langchain.com/
4. **Run all diagnostic scripts** and collect output for debugging

## 🎯 Success Indicators

Your LangSmith tracing is working correctly when you see:

1. ✅ Conversation traces in LangSmith UI within 2-5 minutes
2. ✅ Proper trace hierarchy (parent-child relationships)
3. ✅ Agent execution traces with timing data
4. ✅ Integration call traces (database, AI model calls)
5. ✅ No HTTP 422 errors in logs
6. ✅ Metadata populated with conversation_id, user_id, etc.
7. ✅ Performance metrics available for analysis

---

Last updated: September 2025  
Status: All known issues resolved ✅