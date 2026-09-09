from pathlib import Path
def export_dxf(model,path:Path):
 try: import ezdxf
 except ImportError as exc: raise RuntimeError('DXF export requires ezdxf') from exc
 doc=ezdxf.new('R2010'); [doc.layers.add(name) for name in ('WALLS','OPENINGS','ROOMS','DIMENSIONS','ROOM_LABELS')]; ms=doc.modelspace()
 for wall in model.walls: ms.add_line(wall.start_point_2d,wall.end_point_2d,dxfattribs={'layer':'WALLS'})
 for room in model.rooms: ms.add_lwpolyline(room.boundary_polygon_2d,close=True,dxfattribs={'layer':'ROOMS'})
 doc.saveas(path); ezdxf.readfile(path)
