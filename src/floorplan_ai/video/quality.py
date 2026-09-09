from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class FrameQualityConfig: minimum_width:int=640; minimum_height:int=480; minimum_blur_score:float=20.
def blur_score(path):
 import cv2
 image=cv2.imread(str(path)); return float(cv2.Laplacian(image,cv2.CV_64F).var()) if image is not None else 0.
def filter_frames(frames,config=FrameQualityConfig()):
 import cv2
 accepted=[]; rejected=[]
 for frame in frames:
  image=cv2.imread(str(frame.path)); score=blur_score(frame.path)
  if image is not None and image.shape[1]>=config.minimum_width and image.shape[0]>=config.minimum_height and score>=config.minimum_blur_score: accepted.append(frame)
  else: rejected.append(frame)
 return tuple(accepted if accepted else frames),tuple(rejected)
