# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2025-06-26

### Added
- ✅ **Flexible ProductAgent data source configuration**
  - New environment variables for ProductAgent configuration:
    - `PRODUCT_AGENT_DATA_SOURCE`: Choose between "database" or "dux" mode
    - `PRODUCT_AGENT_SYNC_HOURS`: Configure automatic sync hours (e.g., "2,14" for 2 AM and 2 PM)
    - `PRODUCT_AGENT_FORCE_SYNC_THRESHOLD_HOURS`: Force sync when data is older than X hours
    - `PRODUCT_AGENT_DUX_SEARCH_PAGES`: Max pages for DUX search (future use)

- ✅ **Scheduled synchronization service**
  - New `ScheduledSyncService` for automatic DUX to database synchronization
  - Background task system that respects configured sync hours
  - Intelligent sync based on data age thresholds
  - Integration with FastAPI startup/shutdown events

- ✅ **DUX sync monitoring APIs**
  - `GET /api/v1/dux/sync/status`: Check synchronization status
  - `POST /api/v1/dux/sync/force`: Manually trigger synchronization
  - Real-time sync statistics and next scheduled sync information

### Fixed
- 🐛 **Critical LangGraph message flow bug**
  - Fixed issue where new user messages were being lost in conversation state
  - Previous behavior: Intent router always received the first message ("Hola") from conversation history
  - New behavior: Intent router correctly receives the actual current user message
  - Impact: All agents now process the correct user input instead of cached first message

- 🐛 **Database schema compatibility**
  - Added missing columns to `customers` table: `first_name`, `last_name`, `date_of_birth`, `gender`
  - Fixed PostgreSQL schema validation errors
  - Ensured Customer model compatibility with existing database

- 🐛 **Intent routing and cache issues**
  - Fixed intent router incorrectly caching all messages with same key
  - Resolved all messages being routed to `fallback_agent` instead of specific agents
  - Now correctly routes messages to appropriate agents:
    - Category queries → `category_agent`
    - Product searches → `product_agent`
    - General queries → `fallback_agent`

- 🐛 **WhatsAppMessage validation error**
  - Fixed Pydantic validation error for missing `from` field in chat_direct script
  - Updated message creation to use proper field aliases

### Changed
- ⚡ **Performance optimization: System prompts in English**
  - Migrated internal LLM prompts from Spanish to English for better performance
  - Affected files:
    - `app/agents/langgraph_system/prompts/intent_analyzer.py`
    - `app/schemas/agent_schema.py`
  - User-facing responses remain in Spanish
  - Expected benefits: Better accuracy, faster processing, more consistent responses

- 🔧 **Enhanced debug logging**
  - Added cache key generation logging for troubleshooting
  - Improved error messages in intent router
  - Better visibility into LLM intent analysis process

### Technical Details

#### Database Changes
```sql
ALTER TABLE customers ADD COLUMN IF NOT EXISTS first_name VARCHAR(100);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS last_name VARCHAR(100);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS date_of_birth DATE;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS gender VARCHAR(20);
```

#### Configuration Changes
```env
# New environment variables
PRODUCT_AGENT_DATA_SOURCE=database
PRODUCT_AGENT_SYNC_HOURS=2,14
PRODUCT_AGENT_FORCE_SYNC_THRESHOLD_HOURS=24
PRODUCT_AGENT_DUX_SEARCH_PAGES=10
```

#### LangGraph State Fix
**Before (Bug):**
```python
# This overwrote the new message with old state
initial_state = state_dict  
```

**After (Fixed):**
```python
# This properly merges new message into existing state
state_dict = current_state.values.copy()
new_message = HumanMessage(content=message)
existing_messages = state_dict.get("messages", [])
state_dict["messages"] = existing_messages + [new_message]
initial_state = state_dict
```

### Workflow Validation
- ✅ **Intent Classification Flow**:
  1. User: "¿Qué categorías de productos manejan?" → `category_agent`
  2. User: "Muéstrame laptops" → `product_agent`
  3. User: "Hola" → `fallback_agent`

- ✅ **ProductAgent Data Source Selection**:
  - Database mode: Uses local PostgreSQL with AI-powered search
  - DUX mode: Automatic sync + AI-powered search on synced data

- ✅ **Background Services**:
  - Scheduled sync starts/stops with application lifecycle
  - Only activates when `PRODUCT_AGENT_DATA_SOURCE=dux`

### Breaking Changes
None. All changes are backward compatible.

### Migration Guide
1. Run database initialization to add missing columns:
   ```bash
   python -m app.scripts.init_database
   ```

2. Update `.env` file with new ProductAgent configuration:
   ```env
   PRODUCT_AGENT_DATA_SOURCE=database  # or "dux"
   PRODUCT_AGENT_SYNC_HOURS=2,14
   PRODUCT_AGENT_FORCE_SYNC_THRESHOLD_HOURS=24
   ```

3. Restart application to activate background services

### Contributors
- Enhanced by Claude Code (Anthropic) with user guidance
- Original issue identification and requirements by project maintainer

---

## Previous Versions
*No previous changelog entries available*