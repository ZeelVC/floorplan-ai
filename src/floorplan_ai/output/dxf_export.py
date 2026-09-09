from pathlib import Path


def _point_on_wall(wall, distance):
    length = wall.length
    t = 0.0 if length <= 0 else min(1.0, max(0.0, distance / length))
    return (
        wall.start_point_2d[0] + t * (wall.end_point_2d[0] - wall.start_point_2d[0]),
        wall.start_point_2d[1] + t * (wall.end_point_2d[1] - wall.start_point_2d[1]),
    )


def export_dxf(model, path: Path):
    try:
        import ezdxf
    except ImportError as exc:
        raise RuntimeError("DXF export requires ezdxf") from exc

    doc = ezdxf.new("R2010")
    for name in ("WALLS", "OPENINGS", "ROOMS", "DIMENSIONS", "ROOM_LABELS"):
        if name not in doc.layers:
            doc.layers.add(name)
    ms = doc.modelspace()
    walls = {wall.wall_id: wall for wall in model.walls}

    for wall in model.walls:
        ms.add_line(wall.start_point_2d, wall.end_point_2d, dxfattribs={"layer": "WALLS"})

    for room in model.rooms:
        ms.add_lwpolyline(room.boundary_polygon_2d, close=True, dxfattribs={"layer": "ROOMS"})
        if room.boundary_polygon_2d:
            cx = sum(p[0] for p in room.boundary_polygon_2d) / len(room.boundary_polygon_2d)
            cy = sum(p[1] for p in room.boundary_polygon_2d) / len(room.boundary_polygon_2d)
            ms.add_text(room.room_type, dxfattribs={"layer": "ROOM_LABELS", "height": 0.15}).set_placement((cx, cy))

    for opening in model.openings:
        wall = walls.get(opening.parent_wall_id)
        if wall is None:
            continue
        a = _point_on_wall(wall, opening.offset_along_wall)
        b = _point_on_wall(wall, opening.offset_along_wall + opening.width)
        ms.add_line(a, b, dxfattribs={"layer": "OPENINGS"})

    for measurement in model.measurements:
        if measurement.metric_type != "WALL_LENGTH" and str(measurement.metric_type) != "MeasurementType.WALL_LENGTH":
            continue
        wall = walls.get(measurement.target_entity_id)
        if wall is None:
            continue
        x = (wall.start_point_2d[0] + wall.end_point_2d[0]) / 2
        y = (wall.start_point_2d[1] + wall.end_point_2d[1]) / 2
        sigma = measurement.standard_deviation or 0.0
        label = f"{measurement.nominal_value:.2f} m +/- {1.96 * sigma:.2f}"
        ms.add_text(label, dxfattribs={"layer": "DIMENSIONS", "height": 0.12}).set_placement((x, y))

    doc.saveas(path)
    ezdxf.readfile(path)
