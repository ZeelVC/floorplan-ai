"""Prepare model cache without silently downloading at runtime."""
from __future__ import annotations
import argparse, json
from pathlib import Path

def main(argv=None):
 p=argparse.ArgumentParser(description="Validate/place locally acquired model assets."); p.add_argument('--model-dir',type=Path,default=Path('models')); p.add_argument('--check',action='store_true'); a=p.parse_args(argv)
 manifest=json.loads((Path(__file__).parents[1]/'models/manifest.json').read_text())
 missing=[m['filename'] for m in manifest['models'] if not (a.model_dir/m['filename']).exists()]
 if missing: print('Missing local model assets: '+', '.join(missing)+'\nAcquire them during setup; this command never downloads automatically.'); return 1 if a.check else 0
 print('All declared local model assets are present.'); return 0
if __name__=='__main__': raise SystemExit(main())
