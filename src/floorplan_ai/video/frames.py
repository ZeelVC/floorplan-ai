from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
@dataclass(frozen=True)
class ExtractedFrame: frame_id:str; path:Path; timestamp_seconds:float
def extract_frames(video_path:Path, output_dir:Path, target_fps:float=2,max_frames:int=300)->tuple[ExtractedFrame,...]:
 import cv2
 cap=cv2.VideoCapture(str(video_path)); fps=cap.get(cv2.CAP_PROP_FPS) or target_fps; step=max(1,round(fps/target_fps)); output_dir.mkdir(parents=True,exist_ok=True); frames=[]; n=0; i=0
 while len(frames)<max_frames:
  ok,image=cap.read()
  if not ok: break
  if i%step==0:
   n+=1; path=output_dir/f'frame_{n:06d}.jpg'; cv2.imwrite(str(path),image); frames.append(ExtractedFrame(path.stem,path,i/fps))
  i+=1
 cap.release(); return tuple(frames)
