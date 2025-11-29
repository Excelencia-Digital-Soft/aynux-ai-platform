"""
Vector Helpers.

Single Responsibility: Format and convert vector data for pgvector operations.
"""


def format_vector_for_query(vector: list[float]) -> str:
    """
    Convert vector list to pgvector-compatible string format.

    Args:
        vector: List of floats

    Returns:
        String in format '[val1,val2,...]' for pgvector
    """
    return f"[{','.join(str(v) for v in vector)}]"


def vector_from_string(vector_str: str) -> list[float]:
    """
    Convert pgvector string format back to list.

    Args:
        vector_str: String like '[0.1,0.2,0.3]'

    Returns:
        List of floats
    """
    clean_str = vector_str.strip("[]")
    return [float(v) for v in clean_str.split(",")]
