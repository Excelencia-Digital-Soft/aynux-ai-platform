# Admin User Management - Aynux Production

## Overview

Guía para crear y gestionar usuarios admin en el servidor de producción de Aynux.

## Prerequisitos

- Acceso SSH al servidor de producción
- Docker instalado y contenedores corriendo
- Acceso a PostgreSQL via container `aynux-postgres`

## Verificar Contenedores

```bash
docker ps
```

Contenedores esperados:
- `aynux-prod-app-1` - Aplicación FastAPI
- `aynux-postgres` - Base de datos PostgreSQL
- `aynux-redis` - Cache Redis

---

## Crear Usuario Admin

### Método 1: Via Alembic Migration (Recomendado para nuevos deploys)

Setear `ADMIN_PASSWORD` antes de iniciar el contenedor:

```bash
# Agregar a .env
echo "ADMIN_PASSWORD=tu_password_seguro" >> .env

# Rebuild y restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d app
```

Variables disponibles:

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ADMIN_EMAIL` | admin@aynux.com | Email del admin |
| `ADMIN_PASSWORD` | **(requerido)** | Password |
| `ADMIN_USERNAME` | admin | Username |
| `ADMIN_FULL_NAME` | System Administrator | Nombre completo |

### Método 2: Via SQL Directo (Para sistemas ya deployados)

```bash
docker exec aynux-postgres psql -U enzo -d aynux -c "
INSERT INTO core.users (
    id, username, email, password_hash, full_name, disabled, scopes, created_at, updated_at
) VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,
    'admin',
    'admin@aynux.com',
    '\$2b\$12\$xHZVBVtobNhTI8OlHnmhoeTgk2MPADoo77YvGa8btF3I8wprZE3ke',
    'System Administrator',
    false,
    ARRAY['admin', 'users:read', 'users:write', 'orgs:read', 'orgs:write']::text[],
    NOW(), NOW()
) ON CONFLICT (id) DO NOTHING;
"
```

> **Nota**: El hash anterior corresponde a password `admin1234`

---

## Verificar Usuario

```bash
docker exec aynux-postgres psql -U enzo -d aynux -c \
  "SELECT id, username, email, full_name, disabled FROM core.users;"
```

Output esperado:
```
                  id                  | username |      email       |      full_name       | disabled
--------------------------------------+----------+------------------+----------------------+----------
 00000000-0000-0000-0000-000000000001 | admin    | admin@aynux.com  | System Administrator | f
```

---

## Actualizar Password

### Paso 1: Generar hash bcrypt

En máquina local con Python:

```bash
uv run python -c "import bcrypt; print(bcrypt.hashpw(b'NUEVO_PASSWORD', bcrypt.gensalt()).decode())"
```

O dentro del contenedor de la app:

```bash
docker exec aynux-prod-app-1 python -c "import bcrypt; print(bcrypt.hashpw(b'NUEVO_PASSWORD', bcrypt.gensalt()).decode())"
```

### Paso 2: Actualizar en base de datos

```bash
docker exec aynux-postgres psql -U enzo -d aynux -c \
  "UPDATE core.users SET password_hash = '\$2b\$12\$TU_HASH_AQUI', updated_at = NOW() WHERE username = 'admin';"
```

### Ejemplo completo

Para password `admin1234`:

```bash
docker exec aynux-postgres psql -U enzo -d aynux -c \
  "UPDATE core.users SET password_hash = '\$2b\$12\$xHZVBVtobNhTI8OlHnmhoeTgk2MPADoo77YvGa8btF3I8wprZE3ke', updated_at = NOW() WHERE username = 'admin';"
```

---

## Probar Login

### Via curl

```bash
curl -X POST https://tu-dominio.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@aynux.com", "password": "admin1234"}'
```

### Respuesta esperada

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

---

## Troubleshooting

### Error: "Credenciales incorrectas" (401)

1. Verificar que el usuario existe:
   ```bash
   docker exec aynux-postgres psql -U enzo -d aynux -c \
     "SELECT username, email FROM core.users WHERE email = 'admin@aynux.com';"
   ```

2. Regenerar el password hash y actualizar

### Error: "relation core.users does not exist"

Las migraciones no han corrido. Ejecutar:

```bash
docker exec aynux-prod-app-1 alembic upgrade head
```

### Ver logs de autenticación

```bash
docker logs -f aynux-prod-app-1 2>&1 | grep -i auth
```

---

## Scopes Disponibles

| Scope | Descripción |
|-------|-------------|
| `admin` | Acceso administrativo completo |
| `users:read` | Leer usuarios |
| `users:write` | Crear/editar usuarios |
| `orgs:read` | Leer organizaciones |
| `orgs:write` | Crear/editar organizaciones |

---

## Comandos Útiles

```bash
# Listar todos los usuarios
docker exec aynux-postgres psql -U enzo -d aynux -c \
  "SELECT id, username, email, disabled, scopes FROM core.users;"

# Deshabilitar usuario
docker exec aynux-postgres psql -U enzo -d aynux -c \
  "UPDATE core.users SET disabled = true WHERE username = 'admin';"

# Habilitar usuario
docker exec aynux-postgres psql -U enzo -d aynux -c \
  "UPDATE core.users SET disabled = false WHERE username = 'admin';"

# Eliminar usuario
docker exec aynux-postgres psql -U enzo -d aynux -c \
  "DELETE FROM core.users WHERE username = 'admin';"

# Ver estado de migraciones
docker exec aynux-prod-app-1 alembic current

# Ver historial de migraciones
docker exec aynux-prod-app-1 alembic history
```

---

## Referencias

- Archivo de migración: `alembic/versions/o6i1k90l345j_seed_admin_user.py`
- Modelo de usuario: `app/models/db/user.py`
- Servicio de autenticación: `app/services/token_service.py`
