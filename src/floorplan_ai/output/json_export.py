from pathlib import Path
from floorplan_ai.canonical.schema import CanonicalWorldModel
def export_json(model:CanonicalWorldModel,path:Path): path.write_text(model.to_json())
