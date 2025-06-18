"""
Entidades de negocio DUX
Responsabilidad: Definir estructuras de categorías, marcas y proveedores
"""

from typing import Optional

from pydantic import BaseModel


class DuxRubro(BaseModel):
    """Categoría/Rubro de producto en DUX"""
    id: int
    nombre: str


class DuxSubRubro(BaseModel):
    """Subcategoría de producto en DUX"""
    id: Optional[int] = None
    nombre: Optional[str] = None


class DuxMarca(BaseModel):
    """Marca de producto en DUX"""
    codigo_marca: Optional[str] = None
    marca: Optional[str] = None


class DuxProveedor(BaseModel):
    """Proveedor de producto en DUX"""
    id_proveedor: Optional[int] = None
    proveedor: Optional[str] = None
    tipo_doc: Optional[str] = None
    nro_doc: Optional[int] = None
    provincia: Optional[str] = None
    localidad: Optional[str] = None
    domicilio: Optional[str] = None
    barrio: Optional[str] = None
    cod_postal: Optional[str] = None
    telefono: Optional[str] = None
    fax: Optional[str] = None
    compania_celular: Optional[str] = None
    cel: Optional[str] = None
    persona_contacto: Optional[str] = None
    email: Optional[str] = None
    pagina_web: Optional[str] = None