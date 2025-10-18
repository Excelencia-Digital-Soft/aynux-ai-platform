# Migración ChromaDB → pgvector - Estado Actualizado

**Fecha de inicio**: 16 de octubre de 2025, 20:52 PM
**PID del proceso**: 29459 (wrapper), 29507 (Python)
**Script**: `migrate_chroma_to_pgvector_sync.py` (versión sincrónica con psycopg2)
**Productos totales**: 36,508
**Batch size**: 100 productos por lote
**Modelo de embeddings**: `mxbai-embed-large:latest` (1024 dimensiones)

---

## Estado Actual (21:06 PM)

### ✅ Progreso

**Embeddings generados**: 3,731 / 36,508 (10.2%)
**Productos restantes**: 32,777
**Velocidad promedio**: ~287 productos/minuto (~4.8/segundo)
**Tiempo transcurrido**: ~13 minutos
**Tiempo restante estimado**: ~2 horas

### 🔧 Resolución de Problemas Técnicos

1. **Error greenlet_spawn con asyncpg** ❌
   - Script original fallaba en background por limitaciones de asyncpg
   - Solución: Crear versión sincrónica con psycopg2

2. **Dimensiones de embedding incorrectas** ❌
   - `nomic-embed-text:v1.5` devuelve 768 dimensiones
   - Tabla PostgreSQL configurada para 1024 dimensiones
   - Solución: Cambiar a `mxbai-embed-large:latest` (1024 dimensiones)

3. **Script sincrónico funcionando** ✅
   - Sin problemas de greenlet
   - Ejecutándose exitosamente en background con nohup

---

## Configuración Final

### .env
```bash
USE_PGVECTOR=true
PRODUCT_SEARCH_STRATEGY=pgvector_primary
PGVECTOR_SIMILARITY_THRESHOLD=0.7
OLLAMA_API_MODEL_EMBEDDING=nomic-embed-text  # Compatible con mxbai-embed-large
LANGSMITH_TRACING=false  # Deshabilitado temporalmente por límite mensual
```

### Modelo de Embeddings
- **Modelo activo**: `mxbai-embed-large:latest`
- **Dimensiones**: 1024
- **Compatible con**: PostgreSQL `vector(1024)`

---

## Monitoreo

### Verificar progreso en tiempo real

```bash
# Ver cobertura actual de embeddings
PGPASSWORD="" psql -h localhost -U enzo -d aynux -c "
SELECT
  COUNT(*) as total,
  COUNT(embedding) as with_embedding,
  ROUND(COUNT(embedding)::numeric / COUNT(*)::numeric * 100, 2) as coverage_pct,
  COUNT(*) - COUNT(embedding) as remaining
FROM products
WHERE active = true;
"

# Ver últimos productos con embeddings generados
PGPASSWORD="" psql -h localhost -U enzo -d aynux -c "
SELECT name, embedding_model, last_embedding_update
FROM products
WHERE embedding IS NOT NULL
ORDER BY last_embedding_update DESC
LIMIT 10;
"

# Verificar proceso de migración
ps aux | grep migrate_chroma_to_pgvector_sync

# Ver log en tiempo real
tail -f logs/migration_sync_*.log
```

### Estadísticas esperadas

| Tiempo transcurrido | Embeddings esperados | Progreso |
|---------------------|----------------------|----------|
| 30 minutos          | ~8,600 productos     | 23.5%    |
| 1 hora              | ~17,200 productos    | 47.1%    |
| 1.5 horas           | ~25,800 productos    | 70.7%    |
| 2 horas             | ~34,400 productos    | 94.2%    |
| 2.2 horas           | 36,508 productos     | 100%     |

---

## Post-Migración (Pendiente)

### Verificación de calidad

```bash
# 1. Verificar cobertura final
PGPASSWORD="" psql -h localhost -U enzo -d aynux -c "
SELECT
  COUNT(*) as total,
  COUNT(embedding) as with_embeddings,
  ROUND(COUNT(embedding)::numeric / COUNT(*)::numeric * 100, 2) as coverage_pct
FROM products
WHERE active = true;
"

# 2. Test de búsqueda semántica
curl -X POST "http://localhost:8000/api/v1/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_migration",
    "message": "laptop gamer"
  }'

# 3. Verificar logs de búsqueda pgvector
tail -f logs/app.log | grep "pgvector"
```

### Monitoreo LangSmith

**Nota**: Temporalmente deshabilitado por límite mensual. Habilitar cuando se reinicie el límite:

1. Editar `.env`: `LANGSMITH_TRACING=true`
2. Reiniciar aplicación: `./dev-uv.sh`
3. Acceder a: https://smith.langchain.com
4. Proyecto: "pr-vacant-technician-19"
5. Filtrar por: `product_agent` runs
6. Métricas clave:
   - Average similarity score (target: ≥0.75)
   - Search response time (target: <2s)
   - Success rate (target: ≥95%)

---

## Troubleshooting

### Si la migración se detiene

```bash
# 1. Verificar si el proceso sigue corriendo
ps aux | grep migrate_chroma_to_pgvector_sync

# 2. Si se detuvo, reiniciar desde donde quedó (no re-embebé productos existentes)
nohup uv run python app/scripts/migrate_chroma_to_pgvector_sync.py --batch-size 100 > logs/migration_sync_restart_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# 3. Ver progreso en tiempo real
watch -n 30 'psql -h localhost -U enzo -d aynux -c "SELECT COUNT(embedding) FROM products WHERE active = true AND embedding IS NOT NULL;"'
```

### Verificar errores en el log

```bash
# Ver solo errores
grep -i "error\|exception\|failed" logs/migration_sync_*.log | tail -20

# Ver progreso de batches
grep "Progress:" logs/migration_sync_*.log | tail -10
```

---

## Archivos Creados

### Scripts de Migración

1. **`app/scripts/migrate_chroma_to_pgvector.py`** (async - no funciona en background)
   - Versión original con asyncpg
   - Problema: Error `greenlet_spawn` en background

2. **`app/scripts/migrate_chroma_to_pgvector_sync.py`** (sync - ✅ funciona)
   - Versión sincrónica con psycopg2
   - Solución exitosa para ejecución en background

### Logs de Migración

- `logs/migration_sync_YYYYMMDD_HHMMSS.log` - Log principal de la migración activa
- `logs/migration_*.log` - Logs de intentos anteriores (fallidos)

---

## Próximos Pasos

Una vez completada la migración (100% cobertura):

1. ✅ Verificar cobertura final (objetivo: ≥95%)
2. ✅ Test de búsqueda semántica con queries reales
3. ✅ Monitorear métricas de rendimiento
4. 📝 Documentar learnings y optimizaciones
5. 🔄 Considerar remover dependencia de ChromaDB (después de validación)
6. 🎯 Re-habilitar LangSmith tracing cuando se reinicie el límite mensual

---

## Contacto

Para preguntas o problemas:
- Revisar logs en `logs/migration_sync_*.log`
- Consultar documentación en `docs/PGVECTOR_MIGRATION.md`
- Verificar estado del sistema con health checks
