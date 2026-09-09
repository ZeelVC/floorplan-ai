from pathlib import Path
from floorplan_ai.dataset.models import CaptureInput
from floorplan_ai.frontend.photo import PhotoFrontendConfig,reconstruct_photos
from floorplan_ai.reconstruction.models import ReconstructionResult
class Backend:
 def reconstruct(self,*args,**kwargs): return ReconstructionResult(success=False,backend_name='mock',failure_reason='no matches')
def test_degraded_photo_frontend_writes_valid_canonical(tmp_path):
 model=reconstruct_photos((CaptureInput(capture_id='a',source_type='photo',file='a.jpg'),),tmp_path,PhotoFrontendConfig(reconstruction=Backend()))
 assert len(model.captures)==1 and (tmp_path/'canonical.json').is_file() and (tmp_path/'diagnostics.json').is_file()
