#!/usr/bin/env python3
import importlib.util,shutil,sys
print(f'Python: {sys.version.split()[0]}')
for name in ('numpy','cv2','open3d','scipy'):
 print(f'{name}: '+('available' if importlib.util.find_spec(name) else 'MISSING'))
print('COLMAP: '+(shutil.which('colmap') or 'MISSING (install COLMAP and put colmap on PATH)'))
