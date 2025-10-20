#!/bin/bash
# Check embedding generation progress

echo "=== Embedding Generation Progress ==="
echo "Current time: $(date)"
echo ""

# Check database status
echo "📊 Database Status:"
PGPASSWORD="" psql -h localhost -U enzo -d aynux -c "
SELECT
    COUNT(*) as total_products,
    COUNT(embedding) as with_embeddings,
    COUNT(*) - COUNT(embedding) as missing_embeddings,
    ROUND(100.0 * COUNT(embedding) / COUNT(*), 2) as percentage
FROM products
WHERE active = true;
"

echo ""
echo "📈 Products with stock:"
PGPASSWORD="" psql -h localhost -U enzo -d aynux -c "
SELECT
    COUNT(*) as total_with_stock,
    COUNT(embedding) as with_embeddings,
    ROUND(100.0 * COUNT(embedding) / COUNT(*), 2) as percentage
FROM products
WHERE active = true AND stock > 0;
"

echo ""
echo "📝 Latest log entries:"
tail -5 embedding_full.log 2>/dev/null || echo "No log file yet"

echo ""
echo "🔄 Active processes:"
ps aux | grep "[g]enerate_embeddings" | head -3

echo ""
echo "⏱️  Estimated completion time:"
remaining=$(PGPASSWORD="" psql -h localhost -U enzo -d aynux -t -c "SELECT COUNT(*) FROM products WHERE active = true AND embedding IS NULL;" | tr -d ' ')
echo "Remaining products: $remaining"
echo "Estimated time: ~$(($remaining / 60)) minutes (at 1 embedding/sec)"
