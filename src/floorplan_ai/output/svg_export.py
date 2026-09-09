from pathlib import Path
from xml.etree.ElementTree import Element,SubElement,ElementTree

def export_svg(model,path:Path):
 pts=[p for w in model.walls for p in (w.start_point_2d,w.end_point_2d)] or [(0.,0.),(1.,1.)]; minx,miny=map(min,zip(*pts)); maxx,maxy=map(max,zip(*pts)); margin=.5; scale=100
 svg=Element('svg',xmlns='http://www.w3.org/2000/svg',width=str((maxx-minx+2*margin)*scale),height=str((maxy-miny+2*margin)*scale),viewBox=f'{minx-margin} {-maxy-margin} {maxx-minx+2*margin} {maxy-miny+2*margin}')
 for layer in ('rooms','walls','openings','dimensions','labels'): SubElement(svg,'g',id=layer)
 groups={e.attrib['id']:e for e in svg}
 for room in model.rooms: SubElement(groups['rooms'],'polygon',points=' '.join(f'{x},{-y}' for x,y in room.boundary_polygon_2d),fill='#eef6ff',stroke='#90b5d8',**{'stroke-width':'.02'})
 for w in model.walls: SubElement(groups['walls'],'line',x1=str(w.start_point_2d[0]),y1=str(-w.start_point_2d[1]),x2=str(w.end_point_2d[0]),y2=str(-w.end_point_2d[1]),stroke='#17202a',**{'stroke-width':'.08'})
 for m in model.measurements:
  if str(m.metric_type)=='MeasurementType.WALL_LENGTH' or m.metric_type=='WALL_LENGTH': SubElement(groups['dimensions'],'text',x='0',y='0').text=f'{m.nominal_value:.2f} m ± {1.96*(m.standard_deviation or 0):.2f}'
 ElementTree(svg).write(path,encoding='utf-8',xml_declaration=True)
