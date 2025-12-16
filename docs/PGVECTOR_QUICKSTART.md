# pgvector Quick Start Guide

## 🚀 Quick Migration (5 Steps)

Get pgvector up and running in ~15 minutes.

---

## Step 1: Install pgvector Extension

```bash
# Install extension in PostgreSQL
psql -h localhost -U enzo -d aynux -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Verify installation
psql -h localhost -U enzo -d aynux -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

**Expected Output**:
```
 oid  | extname | extowner | extnamespace | ...
------+---------+----------+--------------+-----
 xxxxx | vector  |       10 |         2200 | ...
```

---

## Step 2: Run Database Migration

```bash
# Add pgvector support to products table
psql -h localhost -U enzo -d aynux -f app/scripts/migrations/001_add_pgvector_support.sql
```

**Expected Output**:
```
CREATE EXTENSION
ALTER TABLE
ALTER TABLE
ALTER TABLE
ALTER TABLE
CREATE INDEX
CREATE FUNCTION
...
```

**Verify Schema**:
```bash
psql -h localhost -U enzo -d aynux -c "
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'products' AND column_name IN ('embedding', 'last_embedding_update');
"
```

---

## Step 3: Update Configuration

Edit your `.env` file:

```bash
# Change embedding model
OLLAMA_API_MODEL_EMBEDDING=nomic-embed-text

# Add pgvector configuration (append to file)
USE_PGVECTOR=true
PRODUCT_SEARCH_STRATEGY=pgvector_primary
PGVECTOR_SIMILARITY_THRESHOLD=0.7
```

**Pull embedding model** (if not already available):
```bash
ollama pull nomic-embed-text
```

---

## Step 4: Restart & Test

```bash
# Restart application to load new configuration
./dev-uv.sh
```

**Test Search** (in another terminal):
```bash
curl -X POST "http://localhost:8001/api/v1/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "message": "quiero una laptop gamer"
  }'
```

**Check Logs**:
```bash
tail -f logs/app.log | grep pgvector
```

**Expected Log Output**:
```
2025-09-30 10:00:00 - app.agents.subagent.product_agent - INFO - Attempting pgvector semantic search...
2025-09-30 10:00:01 - app.agents.integrations.pgvector_integration - INFO - pgvector search found 10 products (similarity >= 0.7)
2025-09-30 10:00:01 - app.agents.subagent.product_agent - INFO - Using pgvector results: 10 products found
```

✅ **Success!** pgvector is now handling product search.

---

## 🧪 Run Tests (Optional)

```bash
# Run all pgvector tests
pytest tests/test_pgvector_integration.py -v

# Expected: All tests should pass
```

---

## 📊 Monitor Quality

### LangSmith Dashboard
1. Visit: https://smith.langchain.com
2. Select project: "aynux-production"
3. Filter by: "product_agent"
4. Monitor:
   - Average similarity scores (target: ≥0.75)
   - Response times (target: <2s)
   - Success rates (target: ≥95%)

### Database Statistics
```bash
# Check embedding coverage
psql -h localhost -U enzo -d aynux -c "
SELECT * FROM product_embedding_stats;
"
```

---

## 🔧 Troubleshooting

### Issue: "pgvector extension not installed"
```bash
# Install extension
psql -h localhost -U enzo -d aynux -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Issue: "No results from pgvector"
```bash
# Check if products have embeddings
psql -h localhost -U enzo -d aynux -c "
SELECT COUNT(*) as total, COUNT(embedding) as with_embeddings
FROM products WHERE active = true;
"
```

### Issue: "Slow searches"
```bash
# Verify HNSW index exists
psql -h localhost -U enzo -d aynux -c "
SELECT indexname FROM pg_indexes
WHERE tablename = 'products' AND indexname LIKE '%embedding%';
"

# Rebuild index if needed
psql -h localhost -U enzo -d aynux -c "
REINDEX INDEX CONCURRENTLY idx_products_embedding_hnsw;
"
```

---

## 📚 More Information

- **Full Migration Guide**: `docs/PGVECTOR_MIGRATION.md`
- **Implementation Details**: `IMPLEMENTATION_SUMMARY.md`
- **Test Suite**: `tests/test_pgvector_integration.py`

---

## ✅ Success Checklist

- [ ] pgvector extension installed
- [ ] Database schema updated
- [ ] Environment configured
- [ ] Application restarted
- [ ] Search working with pgvector
- [ ] Tests passing
- [ ] LangSmith monitoring active

**All checked?** 🎉 You're ready to go!

---

## 🆘 Need Help?

- Check `docs/PGVECTOR_MIGRATION.md` for detailed troubleshooting
- Review logs for error messages
- Test with `pytest tests/test_pgvector_integration.py -v`
- Monitor LangSmith for quality metrics