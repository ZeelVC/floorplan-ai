"""Pure validation helpers used by the canonical spatial schema."""

from __future__ import annotations

from math import isclose, sqrt
from typing import Sequence


SUPPORTED_UNITS = frozenset({"m", "cm", "mm", "ft", "in", "m2", "ft2"})


def require_vector(values: Sequence[float], size: int, name: str) -> tuple[float, ...]:
    if len(values) != size:
        raise ValueError(f"{name} must have {size} components")
    return tuple(float(value) for value in values)


def vector_norm(values: Sequence[float]) -> float:
    return sqrt(sum(float(value) ** 2 for value in values))


def require_unit_vector(values: Sequence[float], size: int, name: str) -> tuple[float, ...]:
    vector = require_vector(values, size, name)
    if not isclose(vector_norm(vector), 1.0, abs_tol=1e-5):
        raise ValueError(f"{name} must be normalized")
    return vector


def require_matrix(matrix: Sequence[Sequence[float]], size: int, name: str) -> tuple[tuple[float, ...], ...]:
    if len(matrix) != size or any(len(row) != size for row in matrix):
        raise ValueError(f"{name} must be a {size}x{size} matrix")
    return tuple(tuple(float(value) for value in row) for row in matrix)


def require_homogeneous_matrix(matrix: Sequence[Sequence[float]], name: str) -> tuple[tuple[float, ...], ...]:
    result = require_matrix(matrix, 4, name)
    if not all(isclose(result[3][index], expected, abs_tol=1e-8) for index, expected in enumerate((0.0, 0.0, 0.0, 1.0))):
        raise ValueError(f"{name} must have final row [0, 0, 0, 1]")
    return result


def polygon_area(points: Sequence[Sequence[float]]) -> float:
    return abs(sum(points[i][0] * points[i + 1][1] - points[i + 1][0] * points[i][1] for i in range(len(points) - 1))) / 2


def _orientation(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(a: Sequence[float], b: Sequence[float], c: Sequence[float], d: Sequence[float]) -> bool:
    # Closed polygons with collinear overlapping non-neighbouring edges are invalid too.
    o1, o2 = _orientation(a, b, c), _orientation(a, b, d)
    o3, o4 = _orientation(c, d, a), _orientation(c, d, b)
    return (o1 * o2 <= 0) and (o3 * o4 <= 0)


def require_simple_closed_polygon(points: Sequence[Sequence[float]], name: str) -> tuple[tuple[float, float], ...]:
    result = tuple(require_vector(point, 2, f"{name} vertex") for point in points)
    if len(result) < 4:
        raise ValueError(f"{name} must contain at least three vertices and a closing vertex")
    if result[0] != result[-1]:
        raise ValueError(f"{name} must be closed (first vertex equals last vertex)")
    if isclose(polygon_area(result), 0.0, abs_tol=1e-12):
        raise ValueError(f"{name} must have non-zero area")
    edges = len(result) - 1
    for i in range(edges):
        for j in range(i + 1, edges):
            if j == i + 1 or (i == 0 and j == edges - 1):
                continue
            if _segments_intersect(result[i], result[i + 1], result[j], result[j + 1]):
                raise ValueError(f"{name} must not self-intersect")
    return result


def determinant_3x3(matrix: Sequence[Sequence[float]]) -> float:
    """Return the determinant of a validated 3x3 matrix."""
    return (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def require_rotation_matrix(matrix: Sequence[Sequence[float]], name: str, tolerance: float = 1e-5) -> None:
    """Validate a proper 3D rotation using RᵀR≈I and det(R)≈+1."""
    rotation = require_matrix(matrix, 3, name)
    for column_a in range(3):
        for column_b in range(3):
            dot_product = sum(rotation[row][column_a] * rotation[row][column_b] for row in range(3))
            expected = 1.0 if column_a == column_b else 0.0
            if not isclose(dot_product, expected, abs_tol=tolerance):
                raise ValueError(f"{name} must satisfy R^T R approximately equal to identity")
    if not isclose(determinant_3x3(rotation), 1.0, abs_tol=tolerance):
        raise ValueError(f"{name} must have determinant approximately +1")


def require_positive_semidefinite(matrix: Sequence[Sequence[float]], name: str, tolerance: float = 1e-10) -> None:
    """Validate a symmetric PSD matrix with an LDLᵀ factorization (no NumPy required)."""
    size = len(matrix)
    lower = [[0.0] * size for _ in range(size)]
    diagonal = [0.0] * size
    for column in range(size):
        pivot = matrix[column][column] - sum(lower[column][k] ** 2 * diagonal[k] for k in range(column))
        if pivot < -tolerance:
            raise ValueError(f"{name} must be positive semidefinite")
        diagonal[column] = 0.0 if abs(pivot) <= tolerance else pivot
        lower[column][column] = 1.0
        for row in range(column + 1, size):
            numerator = matrix[row][column] - sum(
                lower[row][k] * lower[column][k] * diagonal[k] for k in range(column)
            )
            if diagonal[column] == 0.0:
                if abs(numerator) > tolerance:
                    raise ValueError(f"{name} must be positive semidefinite")
            else:
                lower[row][column] = numerator / diagonal[column]
