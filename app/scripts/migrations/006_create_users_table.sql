-- Migration: Create users table for authentication
-- Date: 2025-10-20
-- Author: Leonardo Illanez
-- Description: Tabla para almacenar usuarios del sistema de autenticación con persistencia permanente

-- =====================================================
-- 1. Crear tabla users
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    disabled BOOLEAN DEFAULT FALSE,
    scopes TEXT[] DEFAULT '{}',  -- Array de permisos/roles
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- 2. Crear índices para optimizar búsquedas
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_disabled ON users(disabled);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at DESC);

-- =====================================================
-- 3. Crear trigger para actualizar updated_at automáticamente
-- =====================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 4. Comentarios en la tabla y columnas
-- =====================================================
COMMENT ON TABLE users IS 'Tabla de usuarios del sistema de autenticación con persistencia permanente';
COMMENT ON COLUMN users.id IS 'ID único del usuario (UUID)';
COMMENT ON COLUMN users.username IS 'Nombre de usuario único para login';
COMMENT ON COLUMN users.email IS 'Email único del usuario';
COMMENT ON COLUMN users.password_hash IS 'Hash bcrypt de la contraseña';
COMMENT ON COLUMN users.full_name IS 'Nombre completo del usuario';
COMMENT ON COLUMN users.disabled IS 'Indica si el usuario está deshabilitado';
COMMENT ON COLUMN users.scopes IS 'Array de permisos/roles del usuario';
COMMENT ON COLUMN users.created_at IS 'Fecha de creación del usuario';
COMMENT ON COLUMN users.updated_at IS 'Fecha de última actualización del usuario';

-- =====================================================
-- 5. Crear función para verificar si un usuario existe
-- =====================================================
CREATE OR REPLACE FUNCTION user_exists(p_username VARCHAR)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (SELECT 1 FROM users WHERE username = p_username);
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 6. Crear función para verificar si un email existe
-- =====================================================
CREATE OR REPLACE FUNCTION email_exists(p_email VARCHAR)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (SELECT 1 FROM users WHERE email = p_email);
END;
$$ LANGUAGE plpgsql;
