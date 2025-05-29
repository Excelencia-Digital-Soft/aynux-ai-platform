Si quieres reiniciar la base de datos desde cero, puedes ejecutar:

  # Eliminar todas las tablas
  python -c "from app.database import drop_all_tables; drop_all_tables()"

  # Volver a ejecutar el script de inicialización
  python -m app.scripts.init_database
