# pgvector API Endpoints Documentation

This document describes the API endpoints for managing and monitoring pgvector search functionality.

## Overview

The pgvector API provides endpoints for:
- **Health Monitoring**: Check pgvector availability and performance
- **Embedding Management**: Generate and update product embeddings
- **Search Operations**: Perform semantic similarity searches
- **Statistics & Metrics**: Monitor embedding coverage and quality

## Base URL

```
http://localhost:8001/api/v1
```

## Authentication

All endpoints require authentication via Bearer token:

```http
Authorization: Bearer <your_api_token>
```

---

## Health & Status Endpoints

### Check pgvector Health

Check if pgvector extension is available and functioning correctly.

**Endpoint**: `GET /pgvector/health`

**Response**: `200 OK`
```json
{
  "status": "healthy",
  "pgvector_available": true,
  "embedding_model": "nomic-embed-text",
  "embedding_dimensions": 768,
  "timestamp": "2025-09-30T10:00:00Z"
}
```

**Response**: `503 Service Unavailable`
```json
{
  "status": "unhealthy",
  "pgvector_available": false,
  "error": "pgvector extension not installed",
  "timestamp": "2025-09-30T10:00:00Z"
}
```

**Example**:
```bash
curl -X GET "http://localhost:8001/api/v1/pgvector/health" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### Get Embedding Statistics

Retrieve statistics about embedding coverage across products.

**Endpoint**: `GET /pgvector/statistics`

**Response**: `200 OK`
```json
{
  "total_products": 1500,
  "products_with_embeddings": 1497,
  "products_without_embeddings": 3,
  "coverage_percentage": 99.8,
  "embedding_model": "nomic-embed-text",
  "last_update": "2025-09-30T10:00:00Z",
  "average_embedding_age_days": 2.5,
  "stale_embeddings_count": 15
}
```

**Example**:
```bash
curl -X GET "http://localhost:8001/api/v1/pgvector/statistics" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Embedding Management Endpoints

### Generate Embedding for Single Product

Generate or update the embedding for a specific product.

**Endpoint**: `POST /pgvector/embeddings/product/{product_id}`

**Path Parameters**:
- `product_id` (UUID, required): Product identifier

**Query Parameters**:
- `force` (boolean, optional): Force regeneration even if embedding exists. Default: `false`

**Response**: `200 OK`
```json
{
  "product_id": "123e4567-e89b-12d3-a456-426614174000",
  "success": true,
  "embedding_generated": true,
  "embedding_dimensions": 768,
  "embedding_model": "nomic-embed-text",
  "timestamp": "2025-09-30T10:00:00Z"
}
```

**Response**: `404 Not Found`
```json
{
  "error": "Product not found",
  "product_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

**Example**:
```bash
curl -X POST "http://localhost:8001/api/v1/pgvector/embeddings/product/123e4567-e89b-12d3-a456-426614174000?force=true" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### Batch Generate Embeddings

Generate or update embeddings for multiple products.

**Endpoint**: `POST /pgvector/embeddings/batch`

**Request Body**:
```json
{
  "product_ids": [
    "123e4567-e89b-12d3-a456-426614174000",
    "223e4567-e89b-12d3-a456-426614174001"
  ],
  "force": false,
  "batch_size": 50
}
```

**Request Parameters**:
- `product_ids` (array of UUIDs, optional): Specific products to update. If omitted, processes all products.
- `force` (boolean, optional): Force regeneration even if embeddings exist. Default: `false`
- `batch_size` (integer, optional): Number of products per batch. Default: `50`, Range: `1-100`

**Response**: `200 OK`
```json
{
  "status": "completed",
  "summary": {
    "total": 100,
    "updated": 95,
    "skipped": 3,
    "errors": 2
  },
  "duration_seconds": 45.2,
  "products_per_second": 2.1,
  "timestamp": "2025-09-30T10:00:00Z"
}
```

**Response**: `202 Accepted` (for long-running operations)
```json
{
  "status": "processing",
  "job_id": "batch-job-123",
  "estimated_duration_seconds": 120,
  "check_status_url": "/api/v1/pgvector/embeddings/batch/batch-job-123"
}
```

**Example**:
```bash
# Update specific products
curl -X POST "http://localhost:8001/api/v1/pgvector/embeddings/batch" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "product_ids": ["123e4567-e89b-12d3-a456-426614174000"],
    "force": true,
    "batch_size": 50
  }'

# Update all products missing embeddings
curl -X POST "http://localhost:8001/api/v1/pgvector/embeddings/batch" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "force": false,
    "batch_size": 100
  }'
```

---

### Check Batch Job Status

Check the status of a long-running batch embedding job.

**Endpoint**: `GET /pgvector/embeddings/batch/{job_id}`

**Path Parameters**:
- `job_id` (string, required): Job identifier from batch request

**Response**: `200 OK`
```json
{
  "job_id": "batch-job-123",
  "status": "processing",
  "progress": {
    "current": 50,
    "total": 100,
    "percentage": 50.0
  },
  "summary": {
    "updated": 48,
    "skipped": 1,
    "errors": 1
  },
  "started_at": "2025-09-30T10:00:00Z",
  "estimated_completion": "2025-09-30T10:02:00Z"
}
```

**Example**:
```bash
curl -X GET "http://localhost:8001/api/v1/pgvector/embeddings/batch/batch-job-123" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Search Endpoints

### Semantic Product Search

Perform semantic similarity search across products.

**Endpoint**: `POST /pgvector/search`

**Request Body**:
```json
{
  "query": "laptop gaming con RTX 3070",
  "limit": 10,
  "similarity_threshold": 0.7,
  "filters": {
    "category_id": "cat-123",
    "min_price": 1000.0,
    "max_price": 2000.0,
    "in_stock_only": true,
    "active_only": true
  }
}
```

**Request Parameters**:
- `query` (string, required): Search query text
- `limit` (integer, optional): Maximum results to return. Default: `10`, Range: `1-100`
- `similarity_threshold` (float, optional): Minimum similarity score. Default: `0.7`, Range: `0.0-1.0`
- `filters` (object, optional): Metadata filters
  - `category_id` (UUID, optional): Filter by category
  - `min_price` (float, optional): Minimum price filter
  - `max_price` (float, optional): Maximum price filter
  - `in_stock_only` (boolean, optional): Only in-stock products. Default: `false`
  - `active_only` (boolean, optional): Only active products. Default: `true`

**Response**: `200 OK`
```json
{
  "query": "laptop gaming con RTX 3070",
  "results": [
    {
      "product_id": "123e4567-e89b-12d3-a456-426614174000",
      "sku": "LAPTOP-001",
      "name": "ASUS ROG Strix G15",
      "brand": "ASUS",
      "category": "Gaming Laptops",
      "price": 1599.99,
      "stock": 5,
      "similarity_score": 0.89,
      "description": "High-performance gaming laptop with RTX 3070..."
    },
    {
      "product_id": "223e4567-e89b-12d3-a456-426614174001",
      "sku": "LAPTOP-002",
      "name": "MSI GE76 Raider",
      "brand": "MSI",
      "category": "Gaming Laptops",
      "price": 1799.99,
      "stock": 3,
      "similarity_score": 0.85,
      "description": "Premium gaming laptop with RTX 3070 Ti..."
    }
  ],
  "metadata": {
    "total_results": 2,
    "search_duration_ms": 45.2,
    "similarity_threshold": 0.7,
    "filters_applied": true
  }
}
```

**Response**: `400 Bad Request`
```json
{
  "error": "Invalid query parameter",
  "details": "similarity_threshold must be between 0.0 and 1.0"
}
```

**Example**:
```bash
curl -X POST "http://localhost:8001/api/v1/pgvector/search" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "laptop gaming con RTX 3070",
    "limit": 10,
    "similarity_threshold": 0.7,
    "filters": {
      "in_stock_only": true,
      "min_price": 1000.0,
      "max_price": 2000.0
    }
  }'
```

---

### Similar Products Search

Find products similar to a given product.

**Endpoint**: `GET /pgvector/similar/{product_id}`

**Path Parameters**:
- `product_id` (UUID, required): Reference product identifier

**Query Parameters**:
- `limit` (integer, optional): Maximum results. Default: `10`, Range: `1-100`
- `similarity_threshold` (float, optional): Minimum similarity. Default: `0.6`, Range: `0.0-1.0`
- `exclude_self` (boolean, optional): Exclude reference product. Default: `true`

**Response**: `200 OK`
```json
{
  "reference_product_id": "123e4567-e89b-12d3-a456-426614174000",
  "reference_product_name": "ASUS ROG Strix G15",
  "similar_products": [
    {
      "product_id": "223e4567-e89b-12d3-a456-426614174001",
      "name": "MSI GE76 Raider",
      "similarity_score": 0.92
    },
    {
      "product_id": "323e4567-e89b-12d3-a456-426614174002",
      "name": "Lenovo Legion 5 Pro",
      "similarity_score": 0.87
    }
  ],
  "metadata": {
    "total_results": 2,
    "search_duration_ms": 32.1
  }
}
```

**Example**:
```bash
curl -X GET "http://localhost:8001/api/v1/pgvector/similar/123e4567-e89b-12d3-a456-426614174000?limit=10&similarity_threshold=0.7" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Monitoring & Analytics Endpoints

### Get Performance Metrics

Retrieve performance metrics for pgvector operations.

**Endpoint**: `GET /pgvector/metrics`

**Query Parameters**:
- `time_range` (string, optional): Time range for metrics. Options: `1h`, `24h`, `7d`, `30d`. Default: `24h`

**Response**: `200 OK`
```json
{
  "time_range": "24h",
  "search_metrics": {
    "total_searches": 1250,
    "average_latency_ms": 45.2,
    "p95_latency_ms": 78.5,
    "p99_latency_ms": 95.3,
    "error_rate": 0.002
  },
  "embedding_metrics": {
    "total_updates": 150,
    "average_duration_ms": 320.5,
    "successful_updates": 148,
    "failed_updates": 2
  },
  "quality_metrics": {
    "average_similarity_score": 0.78,
    "low_quality_searches": 25,
    "no_results_count": 10
  },
  "timestamp": "2025-09-30T10:00:00Z"
}
```

**Example**:
```bash
curl -X GET "http://localhost:8001/api/v1/pgvector/metrics?time_range=24h" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### Get Stale Embeddings

Retrieve products with outdated embeddings.

**Endpoint**: `GET /pgvector/embeddings/stale`

**Query Parameters**:
- `threshold_days` (integer, optional): Days since last update. Default: `7`, Range: `1-90`
- `limit` (integer, optional): Maximum results. Default: `100`, Range: `1-1000`

**Response**: `200 OK`
```json
{
  "threshold_days": 7,
  "stale_embeddings": [
    {
      "product_id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "ASUS ROG Strix G15",
      "last_embedding_update": "2025-09-20T10:00:00Z",
      "days_since_update": 10
    },
    {
      "product_id": "223e4567-e89b-12d3-a456-426614174001",
      "name": "MSI GE76 Raider",
      "last_embedding_update": "2025-09-18T10:00:00Z",
      "days_since_update": 12
    }
  ],
  "total_stale": 15,
  "returned": 2
}
```

**Example**:
```bash
curl -X GET "http://localhost:8001/api/v1/pgvector/embeddings/stale?threshold_days=7&limit=100" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request
Invalid request parameters or malformed JSON.

```json
{
  "error": "Bad Request",
  "details": "similarity_threshold must be between 0.0 and 1.0",
  "timestamp": "2025-09-30T10:00:00Z"
}
```

### 401 Unauthorized
Missing or invalid authentication token.

```json
{
  "error": "Unauthorized",
  "details": "Invalid or missing API token",
  "timestamp": "2025-09-30T10:00:00Z"
}
```

### 404 Not Found
Requested resource not found.

```json
{
  "error": "Not Found",
  "details": "Product with ID 123e4567-e89b-12d3-a456-426614174000 not found",
  "timestamp": "2025-09-30T10:00:00Z"
}
```

### 500 Internal Server Error
Server-side error during processing.

```json
{
  "error": "Internal Server Error",
  "details": "Failed to generate embedding: connection timeout",
  "timestamp": "2025-09-30T10:00:00Z"
}
```

### 503 Service Unavailable
pgvector or dependent services unavailable.

```json
{
  "error": "Service Unavailable",
  "details": "pgvector extension not available",
  "timestamp": "2025-09-30T10:00:00Z"
}
```

---

## Rate Limiting

API endpoints are rate-limited to ensure fair usage:

- **Search Endpoints**: 60 requests per minute per API key
- **Embedding Generation**: 30 requests per minute per API key
- **Batch Operations**: 5 requests per minute per API key
- **Monitoring Endpoints**: 120 requests per minute per API key

Rate limit headers are included in responses:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1696075200
```

When rate limit is exceeded:

**Response**: `429 Too Many Requests`
```json
{
  "error": "Rate limit exceeded",
  "retry_after_seconds": 30,
  "timestamp": "2025-09-30T10:00:00Z"
}
```

---

## Best Practices

### Search Optimization
1. **Use appropriate similarity thresholds**: Start with `0.7` for precision, lower to `0.5` for recall
2. **Apply filters**: Use metadata filters to reduce search scope and improve relevance
3. **Limit results**: Request only what you need to minimize response time
4. **Cache results**: Cache frequent queries on client side for better performance

### Embedding Management
1. **Batch operations**: Use batch endpoints for updating multiple products
2. **Schedule updates**: Run batch updates during off-peak hours
3. **Monitor coverage**: Regularly check embedding statistics
4. **Force updates**: Use `force=true` only when necessary to save resources

### Error Handling
1. **Implement retries**: Use exponential backoff for transient errors
2. **Handle rate limits**: Respect rate limit headers and implement queuing
3. **Log errors**: Track failed searches and embedding updates for debugging
4. **Fallback strategy**: Have fallback search methods when pgvector is unavailable

### Performance
1. **Monitor metrics**: Track latency and error rates via metrics endpoint
2. **Set timeouts**: Configure appropriate client-side timeouts (5-10 seconds)
3. **Parallel requests**: Use connection pooling for concurrent requests
4. **Optimize queries**: Use filters to reduce result sets

---

## SDK Examples

### Python Example

```python
import requests
from typing import List, Dict, Optional

class PgVectorClient:
    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_token}"}

    def search_products(
        self,
        query: str,
        limit: int = 10,
        similarity_threshold: float = 0.7,
        filters: Optional[Dict] = None
    ) -> Dict:
        """Perform semantic product search."""
        url = f"{self.base_url}/pgvector/search"
        payload = {
            "query": query,
            "limit": limit,
            "similarity_threshold": similarity_threshold,
            "filters": filters or {}
        }
        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_statistics(self) -> Dict:
        """Get embedding statistics."""
        url = f"{self.base_url}/pgvector/statistics"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def update_embeddings_batch(
        self,
        product_ids: Optional[List[str]] = None,
        force: bool = False,
        batch_size: int = 50
    ) -> Dict:
        """Update embeddings in batch."""
        url = f"{self.base_url}/pgvector/embeddings/batch"
        payload = {
            "product_ids": product_ids,
            "force": force,
            "batch_size": batch_size
        }
        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        return response.json()

# Usage
client = PgVectorClient(
    base_url="http://localhost:8001/api/v1",
    api_token="your_api_token"
)

# Search products
results = client.search_products(
    query="laptop gaming con RTX",
    limit=10,
    similarity_threshold=0.7,
    filters={"in_stock_only": True, "min_price": 1000.0}
)

print(f"Found {len(results['results'])} products")
for product in results['results']:
    print(f"- {product['name']} (similarity: {product['similarity_score']:.2f})")
```

---

## Changelog

### Version 1.0.0 (2025-09-30)
- Initial pgvector API release
- Search, embedding management, and monitoring endpoints
- Rate limiting and error handling
- Performance metrics and analytics

---

## Support

For issues, questions, or feedback:
- **Documentation**: `/docs/PGVECTOR_MIGRATION.md`
- **Health Check**: `GET /pgvector/health`
- **GitHub Issues**: Report bugs and feature requests
- **LangSmith**: Monitor search quality and performance