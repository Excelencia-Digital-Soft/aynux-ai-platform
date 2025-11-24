# Knowledge API Deployment Plan

**Project**: Aynux - Knowledge Base API
**Branch**: `claude/review-knowledge-api-01J5ectMvDf1qXRsu5asZqRv`
**Target Date**: Week of 2025-11-25
**Owner**: Development Team

---

## 📋 Overview

This document outlines the gradual deployment strategy for the Knowledge Base API, including staging validation, monitoring, and production rollout.

---

## 🎯 Deployment Objectives

1. **Zero-downtime deployment** of Knowledge API endpoints
2. **Validate** all 11 API endpoints in staging
3. **Monitor** performance and error rates
4. **Gradual rollout** to production with instant rollback capability
5. **Ensure** backward compatibility with existing systems

---

## 🗓️ Timeline

### Week 1: Staging Deployment & Validation
- **Day 1-2**: Environment setup and initial deployment
- **Day 3-4**: Comprehensive API testing
- **Day 5**: Performance validation and bug fixes

### Week 2: Monitoring & Optimization
- **Day 1-3**: Monitor metrics and logs
- **Day 4-5**: Performance optimization if needed

### Week 3: Production Deployment
- **Day 1-2**: Blue-green deployment setup
- **Day 3**: Gradual traffic rollout (10% → 50%)
- **Day 4-5**: Complete rollout (100%) and monitoring

### Week 4: Post-Deployment
- **Day 1-5**: Intensive monitoring and user feedback collection

---

## 🚀 Phase 1: Staging Deployment (Days 1-2)

### Prerequisites Checklist

- [ ] Staging environment accessible
- [ ] Database credentials configured
- [ ] Ollama service running (for embeddings)
- [ ] Redis available (for caching)
- [ ] PostgreSQL with pgvector extension enabled
- [ ] ChromaDB configured (legacy support)

### Deployment Steps

#### 1. Checkout and Pull Latest Code

```bash
# Ensure on correct branch
git checkout claude/review-knowledge-api-01J5ectMvDf1qXRsu5asZqRv
git pull origin claude/review-knowledge-api-01J5ectMvDf1qXRsu5asZqRv

# Install dependencies
uv sync
```

#### 2. Environment Configuration

Create/update `.env` file with staging values:

```bash
# Database Configuration
DB_HOST=staging-postgres.internal
DB_NAME=aynux_staging
DB_USER=aynux_user
DB_PASSWORD=<staging-password>

# Redis Configuration
REDIS_HOST=staging-redis.internal
REDIS_PORT=6379

# Ollama Configuration (for embeddings)
OLLAMA_API_URL=http://staging-ollama:11434
OLLAMA_API_MODEL_EMBEDDING=nomic-embed-text:v1.5

# Vector Search
USE_PGVECTOR=true
KNOWLEDGE_BASE_ENABLED=true
KNOWLEDGE_SEARCH_STRATEGY=hybrid

# Monitoring
LANGSMITH_API_KEY=<staging-key>
LANGSMITH_PROJECT=aynux-staging
SENTRY_DSN=<staging-sentry-dsn>

# Environment
ENVIRONMENT=staging
```

#### 3. Database Verification

```bash
# Verify pgvector extension
psql -h staging-postgres.internal -U aynux_user -d aynux_staging -c "SELECT * FROM pg_extension WHERE extname='vector';"

# Check company_knowledge table exists
psql -h staging-postgres.internal -U aynux_user -d aynux_staging -c "\d company_knowledge"
```

Expected output:
```
Table "public.company_knowledge"
     Column      |            Type
-----------------+-----------------------------
 id              | uuid
 title           | character varying(500)
 content         | text
 document_type   | character varying(100)
 category        | character varying(200)
 tags            | text[]
 meta_data       | jsonb
 active          | boolean
 sort_order      | integer
 embedding       | vector(1024)
 created_at      | timestamp with time zone
 updated_at      | timestamp with time zone
```

#### 4. Seed Knowledge Base

```bash
# Run seed script
uv run python app/scripts/seed_knowledge_base.py

# Expected output:
# ================================================================================
# Starting knowledge base seeding process
# ================================================================================
#
# Current statistics:
#   Total active documents: 0
#   Embedding coverage: 0.0%
#
# [1/6] Creating: Misión y Visión de Excelencia ERP
#   ✓ Created successfully (ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
#   Embedding generated: True
# ...
# [6/6] Creating: Caso de Éxito: Hospital Central - Implementación HCE
#   ✓ Created successfully (ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
#   Embedding generated: True
#
# ================================================================================
# Seeding process completed
# ================================================================================
#
# Results:
#   ✓ Successfully created: 6
#   ✗ Errors: 0
#
# Final statistics:
#   Total active documents: 6
#   Embedding coverage: 100.0%
#   Embedding model: nomic-embed-text:v1.5
```

#### 5. Start Application

```bash
# Start with uvicorn
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Or use dev script
./dev-uv.sh
# Select option 2 (Start development server)
```

#### 6. Verify API is Running

```bash
# Health check
curl http://localhost:8000/api/v1/admin/knowledge/health

# Expected response:
# {
#   "message": "Knowledge Base API is operational",
#   "success": true,
#   "details": {
#     "active_documents": 6,
#     "embedding_model": "nomic-embed-text:v1.5"
#   }
# }
```

---

## 🧪 Phase 2: API Testing (Days 3-4)

### Test Plan

Use the following test scenarios to validate all endpoints:

#### 1. Health & Statistics Endpoints

```bash
# GET /api/v1/admin/knowledge/health
curl -X GET "http://localhost:8000/api/v1/admin/knowledge/health" \
  -H "accept: application/json"

# GET /api/v1/admin/knowledge/stats
curl -X GET "http://localhost:8000/api/v1/admin/knowledge/stats" \
  -H "accept: application/json"
```

**Expected Results**:
- ✅ Status 200
- ✅ Shows 6 active documents
- ✅ 100% embedding coverage
- ✅ ChromaDB collections populated

#### 2. List Documents (Pagination)

```bash
# GET /api/v1/admin/knowledge?page=1&page_size=10
curl -X GET "http://localhost:8000/api/v1/admin/knowledge?page=1&page_size=10&active_only=true" \
  -H "accept: application/json"
```

**Expected Results**:
- ✅ Status 200
- ✅ Returns 6 documents
- ✅ Pagination metadata correct
- ✅ Documents sorted by `sort_order`

#### 3. Get Single Document

```bash
# GET /api/v1/admin/knowledge/{id}
# First, get an ID from the list endpoint, then:
curl -X GET "http://localhost:8000/api/v1/admin/knowledge/{KNOWLEDGE_ID}" \
  -H "accept: application/json"
```

**Expected Results**:
- ✅ Status 200
- ✅ Complete document returned
- ✅ `has_embedding: true`

#### 4. Search Knowledge Base

```bash
# POST /api/v1/admin/knowledge/search
curl -X POST "http://localhost:8000/api/v1/admin/knowledge/search" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "¿Cuál es la misión de Excelencia?",
    "max_results": 5,
    "search_strategy": "hybrid"
  }'
```

**Expected Results**:
- ✅ Status 200
- ✅ Returns "Misión y Visión" document as top result
- ✅ Similarity scores present
- ✅ Search strategy: "hybrid" confirmed

**Test Different Strategies**:

```bash
# pgvector_primary
curl -X POST "http://localhost:8000/api/v1/admin/knowledge/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "contacto email",
    "max_results": 3,
    "search_strategy": "pgvector_primary"
  }'

# chroma_primary
curl -X POST "http://localhost:8000/api/v1/admin/knowledge/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "historia clínica electrónica",
    "max_results": 3,
    "search_strategy": "chroma_primary"
  }'
```

#### 5. Create Document

```bash
# POST /api/v1/admin/knowledge
curl -X POST "http://localhost:8000/api/v1/admin/knowledge?auto_embed=true" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Preguntas Frecuentes sobre Seguridad de Datos",
    "content": "# Seguridad de Datos en Excelencia ERP\n\n¿Cómo protegemos sus datos?\n\nImplementamos múltiples capas de seguridad:\n\n1. Encriptación en tránsito (TLS 1.3)\n2. Encriptación en reposo (AES-256)\n3. Backups diarios automáticos\n4. Autenticación de dos factores\n5. Auditoría completa de accesos\n\nCumplimos con normativas internacionales de protección de datos.",
    "document_type": "faq",
    "category": "seguridad",
    "tags": ["seguridad", "encriptación", "datos", "privacidad"],
    "metadata": {
      "author": "Security Team",
      "version": "1.0",
      "reviewed_date": "2025-11-24"
    },
    "active": true,
    "sort_order": 100
  }'
```

**Expected Results**:
- ✅ Status 201 Created
- ✅ Returns created document with UUID
- ✅ `has_embedding: true` (auto-generated)
- ✅ Check logs for embedding generation

#### 6. Update Document

```bash
# PUT /api/v1/admin/knowledge/{id}?regenerate_embedding=true
curl -X PUT "http://localhost:8000/api/v1/admin/knowledge/{CREATED_ID}?regenerate_embedding=true" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "FAQ: Seguridad y Privacidad de Datos (Actualizado)",
    "tags": ["seguridad", "encriptación", "datos", "privacidad", "GDPR"]
  }'
```

**Expected Results**:
- ✅ Status 200
- ✅ Updated fields reflected
- ✅ Embedding regenerated (check logs)

#### 7. Regenerate Embeddings

```bash
# POST /api/v1/admin/knowledge/{id}/regenerate-embedding
curl -X POST "http://localhost:8000/api/v1/admin/knowledge/{KNOWLEDGE_ID}/regenerate-embedding?update_pgvector=true&update_chroma=true" \
  -H "accept: application/json"
```

**Expected Results**:
- ✅ Status 200
- ✅ Success message
- ✅ Both pgvector and ChromaDB updated

#### 8. Sync All Embeddings

**⚠️ WARNING**: This can take several minutes for large knowledge bases!

```bash
# POST /api/v1/admin/knowledge/sync-all
curl -X POST "http://localhost:8000/api/v1/admin/knowledge/sync-all?update_pgvector=true&update_chroma=true" \
  -H "accept: application/json"
```

**Expected Results**:
- ✅ Status 200
- ✅ `processed_documents: 7` (6 seeded + 1 created)
- ✅ No errors in logs

#### 9. Delete Document (Soft Delete)

```bash
# DELETE /api/v1/admin/knowledge/{id}?hard_delete=false
curl -X DELETE "http://localhost:8000/api/v1/admin/knowledge/{CREATED_ID}?hard_delete=false" \
  -H "accept: application/json"
```

**Expected Results**:
- ✅ Status 200
- ✅ "deactivated successfully" message
- ✅ Document still exists but `active: false`

#### 10. Delete Document (Hard Delete)

```bash
# DELETE /api/v1/admin/knowledge/{id}?hard_delete=true
curl -X DELETE "http://localhost:8000/api/v1/admin/knowledge/{CREATED_ID}?hard_delete=true" \
  -H "accept: application/json"
```

**Expected Results**:
- ✅ Status 200
- ✅ "deleted successfully" message
- ✅ Document removed from database
- ✅ Embeddings removed from ChromaDB

---

## 📊 Phase 3: Monitoring (Days 1-3 of Week 2)

### Metrics to Track

#### 1. Application Metrics

Monitor via application logs:

```bash
# Watch logs for errors
tail -f logs/aynux.log | grep -i error

# Count API calls per endpoint
grep "GET /api/v1/admin/knowledge" logs/aynux.log | wc -l
grep "POST /api/v1/admin/knowledge/search" logs/aynux.log | wc -l
```

**Key Metrics**:
- API response times (target: < 500ms)
- Embedding generation time (target: < 2s per document)
- Error rate (target: < 0.1%)
- Search result quality (qualitative)

#### 2. Database Performance

```sql
-- Check query performance
SELECT
    query,
    mean_exec_time,
    calls
FROM pg_stat_statements
WHERE query LIKE '%company_knowledge%'
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Check vector index usage
SELECT
    indexname,
    idx_scan,
    idx_tup_read
FROM pg_stat_user_indexes
WHERE tablename = 'company_knowledge';
```

#### 3. LangSmith Tracing

Access LangSmith dashboard:
- Project: `aynux-staging`
- Filter by: `knowledge` tags
- Monitor: Embedding generation traces, search queries

**Expected Patterns**:
- Embedding generation: 1-2 seconds
- Search operations: < 500ms
- No failed traces

#### 4. Sentry Error Tracking

Check Sentry for:
- HTTPExceptions (should be 0 for 500 errors)
- Validation errors (expected for bad requests)
- Database connection issues (should be 0)

---

## 🚀 Phase 4: Production Deployment (Days 1-3 of Week 3)

### Blue-Green Deployment Strategy

#### Step 1: Prepare Blue Environment (Current Production)

```bash
# Tag current production for rollback
git tag production-pre-knowledge-api
git push origin production-pre-knowledge-api
```

#### Step 2: Deploy Green Environment (New Version)

```bash
# Deploy to green environment (inactive)
# Use your deployment tool (e.g., Kubernetes, Docker Compose)

# Verify green environment
curl http://green.aynux.com/api/v1/admin/knowledge/health
```

#### Step 3: Gradual Traffic Rollout

**Day 1: 10% Traffic**
```bash
# Configure load balancer to send 10% to green
# Monitor for 4 hours
# Check error rates, response times
```

**Acceptance Criteria**:
- ✅ Error rate < 0.1%
- ✅ No 500 errors
- ✅ Response times < 500ms
- ✅ No user complaints

**Day 2: 50% Traffic**
```bash
# Increase to 50% if Day 1 successful
# Monitor for 8 hours
```

**Acceptance Criteria**:
- ✅ Same as 10% criteria
- ✅ Database performance stable
- ✅ No memory leaks

**Day 3: 100% Traffic**
```bash
# Switch all traffic to green environment
# Monitor intensively for 24 hours
# Decommission blue environment after 48 hours of stability
```

### Rollback Plan

**Trigger Rollback If**:
- Error rate > 1%
- Any 500 errors detected
- Database performance degradation
- User reports of issues

**Rollback Steps**:
```bash
# Immediate action (< 5 minutes)
1. Switch load balancer back to blue environment
2. Verify blue environment operational
3. Monitor error rates return to normal

# Post-rollback
4. Investigate issue in green environment
5. Fix and re-deploy to staging for validation
6. Retry deployment after fix validated
```

---

## ✅ Post-Deployment Checklist

### Day 1 After Full Rollout

- [ ] All 11 endpoints responding correctly
- [ ] No errors in Sentry
- [ ] LangSmith traces look normal
- [ ] Database queries performing well
- [ ] No user complaints
- [ ] Embedding generation working
- [ ] Search returning relevant results

### Week 1 After Deployment

- [ ] Performance metrics stable
- [ ] No degradation in response times
- [ ] Database growth within expected bounds
- [ ] ChromaDB collections updating correctly
- [ ] Backup/restore tested
- [ ] Documentation updated

### Week 2-4 After Deployment

- [ ] Collect user feedback
- [ ] Identify optimization opportunities
- [ ] Plan next iteration improvements
- [ ] Consider full pgvector migration (remove ChromaDB)

---

## 📞 Escalation Plan

### Issue Severity Levels

**P0 - Critical (Immediate Response)**
- Complete API outage
- Data loss or corruption
- Security breach

**Action**: Immediate rollback + incident call

**P1 - High (1 hour response)**
- Partial API degradation
- High error rates (> 1%)
- Performance issues affecting users

**Action**: Investigate + fix or rollback

**P2 - Medium (4 hour response)**
- Isolated endpoint issues
- Search quality concerns
- Minor performance degradation

**Action**: Investigate + schedule fix

**P3 - Low (Next business day)**
- Documentation issues
- Minor UI inconsistencies
- Enhancement requests

**Action**: Log and prioritize

### Contact Information

- **On-Call Engineer**: [Specify]
- **Database Admin**: [Specify]
- **DevOps Lead**: [Specify]
- **Product Owner**: [Specify]

---

## 📚 Additional Resources

### Documentation Links

- [Knowledge API Code Review](./KNOWLEDGE_API_CODE_REVIEW.md)
- [LangGraph Documentation](./LangGraph.md)
- [Clean Architecture Guide](./CLAUDE.md)
- [Testing Guide](./TESTING_GUIDE.md)

### API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Monitoring Dashboards

- LangSmith: https://smith.langchain.com/
- Sentry: https://sentry.io/
- Application Logs: `/var/log/aynux/`

---

## 🎯 Success Criteria

Deployment is considered successful when:

1. ✅ All 11 endpoints operational in production
2. ✅ Error rate < 0.1% sustained for 7 days
3. ✅ Response times < 500ms (p95)
4. ✅ Embedding generation < 2s per document
5. ✅ Zero critical bugs reported
6. ✅ Search quality meets user expectations
7. ✅ No rollbacks required
8. ✅ 100% uptime maintained

---

**Plan Owner**: Development Team
**Last Updated**: 2025-11-24
**Version**: 1.0
**Status**: Ready for Execution ✅
