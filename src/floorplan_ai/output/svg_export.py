from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree


def _point_on_wall(wall, distance):
    length = wall.length
    if length <= 0:
        return wall.start_point_2d
    t = min(1.0, max(0.0, distance / length))
    return (
        wall.start_point_2d[0] + t * (wall.end_point_2d[0] - wall.start_point_2d[0]),
        wall.start_point_2d[1] + t * (wall.end_point_2d[1] - wall.start_point_2d[1]),
    )


def export_svg(model, path: Path):
    pts = [p for w in model.walls for p in (w.start_point_2d, w.end_point_2d)] or [(0.0, 0.0), (1.0, 1.0)]
    minx, miny = map(min, zip(*pts))
    maxx, maxy = map(max, zip(*pts))
    margin = 0.5
    scale = 100
    width = maxx - minx + 2 * margin
    height = maxy - miny + 2 * margin
    svg = Element(
        "svg",
        xmlns="http://www.w3.org/2000/svg",
        width=str(width * scale),
        height=str(height * scale),
        viewBox=f"{minx-margin} {-maxy-margin} {width} {height}",
    )
    for layer in ("rooms", "walls", "openings", "dimensions", "labels"):
        SubElement(svg, "g", id=layer)
    groups = {e.attrib["id"]: e for e in svg}

    for room in model.rooms:
        SubElement(
            groups["rooms"],
            "polygon",
            points=" ".join(f"{x},{-y}" for x, y in room.boundary_polygon_2d),
            fill="#eef6ff",
            stroke="#90b5d8",
            **{"stroke-width": ".02"},
        )

    walls = {wall.wall_id: wall for wall in model.walls}
    for wall in model.walls:
        SubElement(
            groups["walls"],
            "line",
            x1=str(wall.start_point_2d[0]),
            y1=str(-wall.start_point_2d[1]),
            x2=str(wall.end_point_2d[0]),
            y2=str(-wall.end_point_2d[1]),
            stroke="#17202a",
            **{"stroke-width": ".08"},
        )

    for opening in model.openings:
        wall = walls.get(opening.parent_wall_id)
        if wall is None:
            continue
        a = _point_on_wall(wall, opening.offset_along_wall)
        b = _point_on_wall(wall, opening.offset_along_wall + opening.width)
        SubElement(
            groups["openings"],
            "line",
            x1=str(a[0]), y1=str(-a[1]), x2=str(b[0]), y2=str(-b[1]),
            stroke="#ffffff", **{"stroke-width": ".12"},
        )

    for room in model.rooms:
        if not room.boundary_polygon_2d:
            continue
        cx = sum(p[0] for p in room.boundary_polygon_2d) / len(room.boundary_polygon_2d)
        cy = sum(p[1] for p in room.boundary_polygon_2d) / len(room.boundary_polygon_2d)
        SubElement(groups["labels"], "text", x=str(cx), y=str(-cy), **{"font-size": ".15"}).text = room.room_type

    for measurement in model.measurements:
        if measurement.metric_type != "WALL_LENGTH" and str(measurement.metric_type) != "MeasurementType.WALL_LENGTH":
            continue
        wall = walls.get(measurement.target_entity_id)
        if wall is None:
            continue
        x = (wall.start_point_2d[0] + wall.end_point_2d[0]) / 2
        y = (wall.start_point_2d[1] + wall.end_point_2d[1]) / 2
        sigma = measurement.standard_deviation or 0.0
        SubElement(groups["dimensions"], "text", x=str(x), y=str(-y), **{"font-size": ".12"}).text = (
            f"{measurement.nominal_value:.2f} m ± {1.96 * sigma:.2f}"
        )

    ElementTree(svg).write(path, encoding="utf-8", xml_declaration=True)
