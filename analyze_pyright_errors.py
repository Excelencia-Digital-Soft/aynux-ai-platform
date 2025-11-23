#!/usr/bin/env python3
"""
Script para analizar errores de Pyright y generar reporte clasificado.

Este script ejecuta Pyright, clasifica los errores por tipo y genera
un reporte prioritizado para facilitar la resolución.
"""

import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


def run_pyright():
    """Ejecuta Pyright y retorna el output JSON."""
    try:
        result = subprocess.run(
            ["pyright", "app/", "--outputjson"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error ejecutando Pyright: {e}")
        sys.exit(1)


def classify_diagnostic(diagnostic):
    """Clasifica un diagnóstico de Pyright por tipo."""
    message = diagnostic.get("message", "")

    # Clasificación por tipo de error
    if "could not be resolved" in message.lower():
        return "import_error"
    elif "cannot access attribute" in message.lower():
        return "attribute_error"
    elif "argument of type" in message.lower():
        return "type_mismatch"
    elif "is not assignable" in message.lower():
        return "assignment_error"
    elif "is unknown" in message.lower():
        return "unknown_type"
    elif "missing" in message.lower():
        return "missing_member"
    elif "incompatible" in message.lower():
        return "incompatible_type"
    elif "cannot instantiate" in message.lower():
        return "instantiation_error"
    else:
        return "other"


def generate_report(data):
    """Genera un reporte detallado de los errores."""

    summary = data.get("summary", {})
    diagnostics = data.get("generalDiagnostics", [])

    # Estadísticas generales
    print("=" * 80)
    print("REPORTE DE ANÁLISIS PYRIGHT")
    print("=" * 80)
    print(f"\n📊 RESUMEN GENERAL:")
    print(f"  - Archivos analizados: {summary.get('filesAnalyzed', 0)}")
    print(f"  - Errores: {summary.get('errorCount', 0)}")
    print(f"  - Warnings: {summary.get('warningCount', 0)}")
    print(f"  - Informaciones: {summary.get('informationCount', 0)}")

    # Clasificar diagnósticos
    errors = [d for d in diagnostics if d.get("severity") == "error"]
    warnings = [d for d in diagnostics if d.get("severity") == "warning"]

    # Clasificar errores por tipo
    error_types = Counter([classify_diagnostic(e) for e in errors])

    print(f"\n🔍 CLASIFICACIÓN DE ERRORES:")
    for error_type, count in error_types.most_common():
        percentage = (count / len(errors) * 100) if errors else 0
        print(f"  - {error_type:20s}: {count:4d} ({percentage:5.1f}%)")

    # Archivos con más errores
    file_errors = defaultdict(int)
    for error in errors:
        file_path = Path(error.get("file", "")).relative_to(Path.cwd())
        file_errors[str(file_path)] += 1

    print(f"\n📁 TOP 10 ARCHIVOS CON MÁS ERRORES:")
    for file_path, count in sorted(file_errors.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  - {file_path:60s}: {count:3d} errores")

    # Ejemplos de cada tipo de error
    print(f"\n📝 EJEMPLOS DE ERRORES POR TIPO (primeros 3 de cada tipo):")

    errors_by_type = defaultdict(list)
    for error in errors:
        error_type = classify_diagnostic(error)
        errors_by_type[error_type].append(error)

    for error_type, type_errors in sorted(errors_by_type.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"\n  {error_type.upper()} ({len(type_errors)} total):")
        for error in type_errors[:3]:
            file_path = Path(error.get("file", "")).relative_to(Path.cwd())
            line = error.get("range", {}).get("start", {}).get("line", 0) + 1
            message = error.get("message", "")[:80]
            print(f"    {file_path}:{line}")
            print(f"      → {message}")

    # Recomendaciones
    print(f"\n💡 RECOMENDACIONES:")

    if error_types.get("import_error", 0) > 100:
        print(f"  1. ⚠️  Muchos errores de imports ({error_types['import_error']})")
        print(f"     → Verificar que todas las dependencias estén instaladas")
        print(f"     → Configurar python.pythonPath en Pyright")

    if error_types.get("attribute_error", 0) > 50:
        print(f"  2. ⚠️  Muchos errores de atributos ({error_types['attribute_error']})")
        print(f"     → Mejorar type hints en funciones")
        print(f"     → Usar TypedDict o dataclasses para diccionarios")

    if error_types.get("type_mismatch", 0) > 50:
        print(f"  3. ⚠️  Muchos type mismatches ({error_types['type_mismatch']})")
        print(f"     → Revisar type hints en signatures de funciones")
        print(f"     → Usar Union types o Optional donde sea apropiado")

    # Archivos prioritarios para corregir (excluyendo import errors)
    priority_files = []
    for file_path, errors_list in errors_by_type.items():
        if file_path != "import_error":
            for error in errors_list:
                file = Path(error.get("file", "")).relative_to(Path.cwd())
                priority_files.append(str(file))

    priority_counter = Counter(priority_files)

    if priority_counter:
        print(f"\n🎯 ARCHIVOS PRIORITARIOS PARA CORREGIR (sin imports):")
        for file_path, count in priority_counter.most_common(5):
            print(f"  - {file_path:60s}: {count:3d} errores de tipo")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    print("Ejecutando Pyright...")
    data = run_pyright()
    generate_report(data)
