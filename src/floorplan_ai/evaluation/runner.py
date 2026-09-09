from pathlib import Path
import json
from floorplan_ai.canonical.schema import CanonicalWorldModel
def evaluate(prediction:Path,ground_truth:Path,report_out:Path):
 p=CanonicalWorldModel.from_json(prediction.read_text()); g=CanonicalWorldModel.from_json(ground_truth.read_text()); n=min(len(p.walls),len(g.walls)); errors=[abs(p.walls[i].length-g.walls[i].length) for i in range(n)]; report={'matched_walls':n,'mean_wall_length_absolute_error_m':sum(errors)/n if n else None,'prediction_rooms':len(p.rooms),'ground_truth_rooms':len(g.rooms)}; report_out.write_text(json.dumps(report,indent=2,sort_keys=True)); return report
