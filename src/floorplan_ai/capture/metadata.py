from __future__ import annotations
from pathlib import Path
from typing import Any

def photo_metadata(path:Path)->dict[str,Any]:
    try:
        from PIL import Image, ExifTags
        with Image.open(path) as image:
            exif={ExifTags.TAGS.get(k,k):v for k,v in image.getexif().items()}; result={'width':image.width,'height':image.height}
            for k,out in [('FocalLength','focal_length'),('FocalLengthIn35mmFilm','focal_length_35mm'),('Make','make'),('Model','model'),('Orientation','orientation')]:
                if k in exif: result[out]=float(exif[k]) if k=='FocalLength' and not isinstance(exif[k],float) else exif[k]
            return result
    except Exception:return {}
def video_metadata(path:Path)->dict[str,Any]:
    try:
        import cv2
        cap=cv2.VideoCapture(str(path)); fps=cap.get(cv2.CAP_PROP_FPS); count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); cap.release()
        return {'frame_rate':fps,'frame_count':count,'width':width,'height':height,'duration':count/fps if fps else None}
    except Exception:return {}
