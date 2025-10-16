# pgvector Migration Guide

## Overview

This guide covers the migration from ChromaDB to PostgreSQL pgvector for product semantic search. The migration enables native SQL vector similarity search with better performance, integration, and maintainability.

## Benefits of pgvector

### Performance
- **Sub-100ms searches** with HNSW indexing
- **Metadata filtering during search** (not post-processing)
- **Native PostgreSQL query optimization**
- **Better scalability** for production workloads

### Architecture
- **Single database** - no external vector DB required
- **Transactional consistency** with product data
- **Simplified data pipeline**: DUX → PostgreSQL (embeddings stored directly)
- **Standard SQL queries** - easier to maintain and debug

### Quality
- **Higher similarity threshold** (0.7 vs 0.5) for better precision
- **Integrated metadata filtering** improves relevance
- **Better semantic understanding** with nomic-embed-text model
- **LangSmith quality metrics** for continuous monitoring

## Pre-Migration Checklist

### 1. Database Preparation
```bash
# Install pgvector extension in PostgreSQL
psql -h localhost -U enzo -d aynux -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run migration script to add pgvector support
psql -h localhost -U enzo -d aynux -f app/scripts/migrations/001_add_pgvector_support.sql

# Verify extension installed
psql -h localhost -U enzo -d aynux -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

### 2. Environment Configuration
Update your `.env` file with the following settings:

```bash
# AI Service Settings
OLLAMA_API_MODEL_EMBEDDING=nomic-embed-text

# Vector Search Configuration
USE_PGVECTOR=true
PRODUCT_SEARCH_STRATEGY=pgvector_primary
PGVECTOR_SIMILARITY_THRESHOLD=0.7
CHROMA_SIMILARITY_THRESHOLD=0.5
```

### 3. Backup Existing Data
```bash
# Backup PostgreSQL database
pg_dump -h localhost -U enzo -d aynux -F c -f aynux_backup_$(date +%Y%m%d).dump

# Backup ChromaDB data (optional)
tar -czf chroma_backup_$(date +%Y%m%d).tar.gz data/vector_db/
```

## Migration Process

### Step 1: Run Migration Script (Dry Run)
Test the migration without making changes:

```bash
# Dry run to see migration plan
uv run python app/scripts/migrate_chroma_to_pgvector.py --dry-run
```

Expected output:
```
[Step 1/6] Running pre-flight checks...
  ✓ pgvector extension available
  ✓ ChromaDB collection 'products_all_products' found
  ✓ Database connection successful

[Step 2/6] Analyzing current state...
  Total products in database: 1500
  Products with ChromaDB embeddings: 1200
  Products with pgvector embeddings: 0
  Products missing pgvector embeddings: 1500

[Step 3/6] Building migration plan...
  Would migrate 1500 products (DRY RUN)
```

### Step 2: Execute Migration
Run the actual migration:

```bash
# Full migration with default batch size (50 products per batch)
uv run python app/scripts/migrate_chroma_to_pgvector.py

# Custom batch size for faster processing
uv run python app/scripts/migrate_chroma_to_pgvector.py --batch-size 100

# Force re-embedding even if embeddings exist
uv run python app/scripts/migrate_chroma_to_pgvector.py --force

# Skip verification step
uv run python app/scripts/migrate_chroma_to_pgvector.py --no-verify
```

Expected progress:
```
[Step 4/6] Migrating 1500 products...
  Processing batch 1/30 (50 products)...
  Progress: 50/1500 (3.3%) - Migrated: 48, Errors: 2
  Processing batch 2/30 (50 products)...
  Progress: 100/1500 (6.7%) - Migrated: 97, Errors: 3
  ...
```

### Step 3: Verify Migration
The script automatically verifies migration integrity:

```
[Step 5/6] Verifying migration integrity...
  Products with pgvector embeddings after migration: 1497
  Expected embeddings: 1497
  Running spot checks on random products...
  ✓ ASUS ROG Strix G15 has valid embedding
  ✓ Dell Latitude 3420 has valid embedding
  ✓ Lenovo ThinkPad T14 has valid embedding
```

### Step 4: Review Migration Report
Check the final summary:

```
MIGRATION SUMMARY
================================================================================
Duration: 342.56 seconds

Total products: 1500
Successfully migrated: 1497
Skipped: 0
Errors: 3

Final pgvector coverage: 99.8%

Next Steps:
1. Verify search quality with test queries
2. Update environment variables:
   USE_PGVECTOR=true
   PRODUCT_SEARCH_STRATEGY=pgvector_primary
3. Monitor LangSmith for search quality metrics
4. Consider keeping ChromaDB as fallback initially
```

## Post-Migration Tasks

### 1. Test Product Search
Test semantic search with various queries:

```bash
# Test via API
curl -X POST "http://localhost:8000/api/v1/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "message": "quiero una laptop gamer"
  }'

# Check logs for pgvector usage
tail -f logs/app.log | grep pgvector
```

Expected log output:
```
2025-09-30 10:00:00 - app.agents.subagent.product_agent - INFO - Attempting pgvector semantic search...
2025-09-30 10:00:01 - app.agents.integrations.pgvector_integration - INFO - pgvector search found 10 products (similarity >= 0.7)
2025-09-30 10:00:01 - app.agents.subagent.product_agent - INFO - Using pgvector results: 10 products found
```

### 2. Monitor Search Quality

#### LangSmith Dashboard
Monitor conversation quality in LangSmith:
- Navigate to https://smith.langchain.com
- Select project "aynux-production"
- Filter by "product_agent" runs
- Check similarity scores and user feedback

#### Key Metrics to Monitor
- **Average similarity score**: Should be ≥0.75 with pgvector
- **Product relevance**: Verify results match user queries
- **Response time**: Should be <2s for product search
- **Error rate**: Should be <1% for vector searches

### 3. A/B Testing (Optional)
Compare pgvector vs ChromaDB performance:

```bash
# Test ChromaDB (set strategy to chroma_primary)
export PRODUCT_SEARCH_STRATEGY=chroma_primary

# Test pgvector (set strategy to pgvector_primary)
export PRODUCT_SEARCH_STRATEGY=pgvector_primary

# Test hybrid (try both, use best results)
export PRODUCT_SEARCH_STRATEGY=hybrid
```

## Troubleshooting

### Migration Errors

#### Error: "pgvector extension not installed"
**Solution**:
```bash
# Install pgvector extension
psql -h localhost -U enzo -d aynux -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### Error: "products.embedding column not found"
**Solution**:
```bash
# Run schema migration
psql -h localhost -U enzo -d aynux -f app/scripts/migrations/001_add_pgvector_support.sql
```

#### Error: "Embedding dimension mismatch"
**Solution**:
```bash
# Verify embedding model configuration
echo $OLLAMA_API_MODEL_EMBEDDING  # Should be "nomic-embed-text"

# Verify model is available
curl http://localhost:11434/api/tags | grep nomic-embed-text

# Pull model if missing
ollama pull nomic-embed-text
```

### Search Quality Issues

#### Poor Search Results (Low Similarity Scores)
**Possible causes**:
1. Embeddings not properly generated
2. Query text too short or vague
3. Similarity threshold too high

**Solutions**:
```bash
# 1. Re-generate embeddings with force flag
uv run python app/scripts/migrate_chroma_to_pgvector.py --force

# 2. Adjust similarity threshold in .env
PGVECTOR_SIMILARITY_THRESHOLD=0.6  # Lower threshold for more recall

# 3. Restart application to reload settings
./dev-uv.sh
```

#### No Results Found
**Possible causes**:
1. Products missing embeddings
2. Similarity threshold too strict
3. Metadata filters too restrictive

**Solutions**:
```bash
# Check embedding coverage
psql -h localhost -U enzo -d aynux -c "
SELECT
  COUNT(*) as total_products,
  COUNT(embedding) as with_embeddings,
  COUNT(*) - COUNT(embedding) as missing_embeddings
FROM products
WHERE active = true;
"

# View products missing embeddings
psql -h localhost -U enzo -d aynux -c "
SELECT id, name
FROM products
WHERE active = true AND embedding IS NULL
LIMIT 10;
"

# Run migration for specific products
uv run python app/scripts/migrate_chroma_to_pgvector.py
```

### Performance Issues

#### Slow Search Queries (>2s)
**Solutions**:
```bash
# 1. Check if HNSW index exists
psql -h localhost -U enzo -d aynux -c "
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'products' AND indexname LIKE '%embedding%';
"

# 2. Rebuild index if needed
psql -h localhost -U enzo -d aynux -c "
DROP INDEX IF EXISTS idx_products_embedding_hnsw;
CREATE INDEX idx_products_embedding_hnsw
ON products USING hnsw (embedding vector_cosine_ops);
"

# 3. Run ANALYZE to update statistics
psql -h localhost -U enzo -d aynux -c "ANALYZE products;"
```

#### High Memory Usage
**Solutions**:
```bash
# Check pgvector memory usage
psql -h localhost -U enzo -d aynux -c "
SELECT
  pg_size_pretty(pg_total_relation_size('products')) as table_size,
  pg_size_pretty(pg_relation_size('idx_products_embedding_hnsw')) as index_size;
"

# Consider using IVFFlat index for large datasets (faster build, slower search)
# See migration script for IVFFlat index creation
```

## Rollback Procedure

If you need to rollback to ChromaDB:

### 1. Update Environment Variables
```bash
# Disable pgvector
USE_PGVECTOR=false
PRODUCT_SEARCH_STRATEGY=chroma_primary
```

### 2. Restart Application
```bash
# Restart to reload settings
./dev-uv.sh
```

### 3. Complete Rollback (Optional)
If you need to remove pgvector completely:

```bash
# Remove pgvector schema changes (WARNING: This deletes all embeddings)
psql -h localhost -U enzo -d aynux -c "
DROP MATERIALIZED VIEW IF EXISTS product_embedding_stats CASCADE;
DROP TRIGGER IF EXISTS trigger_update_embedding_version ON products;
DROP FUNCTION IF EXISTS update_embedding_version();
DROP FUNCTION IF EXISTS find_similar_products;
DROP FUNCTION IF EXISTS product_similarity(UUID, UUID);
DROP INDEX IF EXISTS idx_products_embedding_hnsw;
DROP INDEX IF EXISTS idx_products_embedding_update;
DROP INDEX IF EXISTS idx_products_stale_embeddings;
DROP INDEX IF EXISTS idx_products_category_brand_stock;
ALTER TABLE products DROP COLUMN IF EXISTS embedding;
ALTER TABLE products DROP COLUMN IF EXISTS last_embedding_update;
ALTER TABLE products DROP COLUMN IF EXISTS embedding_model;
ALTER TABLE products DROP COLUMN IF EXISTS embedding_version;
DROP EXTENSION IF EXISTS vector CASCADE;
"
```

## Maintenance

### Regular Tasks

#### Update Embeddings for New Products
Embeddings are automatically generated when products are created/updated via the DUX sync process. To manually update:

```bash
# Update embeddings for all products missing them
uv run python app/scripts/migrate_chroma_to_pgvector.py

# Update embeddings for specific products (force refresh)
uv run python app/scripts/migrate_chroma_to_pgvector.py --force
```

#### Monitor Embedding Coverage
```bash
# Check embedding statistics
psql -h localhost -U enzo -d aynux -c "
SELECT * FROM product_embedding_stats;
"

# Refresh materialized view
psql -h localhost -U enzo -d aynux -c "
REFRESH MATERIALIZED VIEW CONCURRENTLY product_embedding_stats;
"
```

#### Optimize Index Performance
```bash
# Rebuild index periodically (monthly recommended)
psql -h localhost -U enzo -d aynux -c "
REINDEX INDEX CONCURRENTLY idx_products_embedding_hnsw;
"

# Update statistics
psql -h localhost -U enzo -d aynux -c "
ANALYZE products;
"
```

## Best Practices

### 1. Embedding Generation
- Use consistent embedding model (nomic-embed-text recommended)
- Include product name, brand, category, description in embedding text
- Update embeddings when product data changes significantly
- Monitor embedding quality with LangSmith metrics

### 2. Search Configuration
- Start with pgvector_primary strategy for best results
- Use similarity threshold ≥0.7 for precision
- Implement metadata filtering for better relevance
- Monitor and adjust thresholds based on user feedback

### 3. Performance Optimization
- Keep HNSW index up to date
- Run ANALYZE regularly (weekly recommended)
- Monitor query performance in LangSmith
- Scale PostgreSQL resources as product catalog grows

### 4. Quality Monitoring
- Track average similarity scores (target: ≥0.75)
- Monitor user feedback and conversation outcomes
- Review LangSmith traces for failed searches
- Conduct regular A/B testing to validate improvements

## Support and Resources

- **LangSmith Dashboard**: https://smith.langchain.com
- **pgvector Documentation**: https://github.com/pgvector/pgvector
- **Project Documentation**: docs/
- **Issue Tracking**: GitHub Issues

## Next Steps

After successful migration:

1. ✅ Monitor search quality for 1-2 weeks
2. ✅ Collect user feedback on product recommendations
3. ✅ Fine-tune similarity thresholds based on metrics
4. ✅ Consider removing ChromaDB fallback after validation
5. ✅ Document any custom optimizations or learnings
6. ✅ Train team on pgvector maintenance procedures