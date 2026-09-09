#!/usr/bin/env python3
import importlib.util,shutil,sys
print(f'Python: AVAILABLE ({sys.version.split()[0]})')
for name in ('numpy','cv2','open3d','scipy'):
 print(f'{name}: '+('AVAILABLE' if importlib.util.find_spec(name) else 'MISSING'))
print('COLMAP: '+('AVAILABLE ('+shutil.which('colmap')+')' if shutil.which('colmap') else 'MISSING (install COLMAP and put colmap on PATH)'))
