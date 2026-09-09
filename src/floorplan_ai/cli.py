"""Command-line interface for the local, offline-first floorplan pipeline."""
from __future__ import annotations
import argparse
from pathlib import Path
from collections.abc import Sequence
from floorplan_ai import __version__

def build_parser():
 p=argparse.ArgumentParser(prog='floorplan-ai',description='Indoor metric floor-plan reconstruction tooling.'); p.add_argument('--version',action='version',version=f'%(prog)s {__version__}'); subs=p.add_subparsers(dest='command')
 r=subs.add_parser('reconstruct',help='reconstruct a photo or video capture'); r.add_argument('--input',required=True,type=Path); r.add_argument('--output',required=True,type=Path); r.add_argument('--disable-drift-correction',action='store_true')
 e=subs.add_parser('evaluate',help='evaluate one or more predictions against ground truth'); e.add_argument('--prediction',required=True,type=Path,nargs='+'); e.add_argument('--ground-truth',required=True,type=Path,nargs='+'); e.add_argument('--report-out',required=True,type=Path)
 w=subs.add_parser('readiness',help='validate a completed reconstruction for unseen-property use'); w.add_argument('--output',required=True,type=Path); w.add_argument('--report-out',type=Path)
 f=subs.add_parser('fetch-models',help='validate/model setup helper'); f.add_argument('--model-dir',type=Path,default=Path('models')); f.add_argument('--check',action='store_true')
 for command in ('perceive-photo','perceive-video','perceive'):
  sub=subs.add_parser(command); sub.add_argument('--input',required=True); sub.add_argument('--output',required=True)
  if command=='perceive': sub.add_argument('--source',choices=('auto','photo','video'),default='auto')
 return p

def main(argv:Sequence[str]|None=None):
 a=build_parser().parse_args(argv)
 if not a.command:return 0
 try:
  if a.command=='reconstruct':
   from floorplan_ai.pipeline import PipelineConfig,run_reconstruction; run_reconstruction(a.input,a.output,PipelineConfig(disable_drift_correction=a.disable_drift_correction))
  elif a.command=='evaluate':
   from floorplan_ai.evaluation import evaluate, evaluate_suite
   if len(a.prediction) == len(a.ground_truth) == 1:
    evaluate(a.prediction[0],a.ground_truth[0],a.report_out)
   else:
    evaluate_suite(a.prediction,a.ground_truth,a.report_out)
  elif a.command=='readiness':
   from floorplan_ai.evaluation.readiness import validate_output
   report=validate_output(a.output)
   report_out=a.report_out or (a.output/'readiness.json')
   report_out.parent.mkdir(parents=True,exist_ok=True)
   import json; report_out.write_text(json.dumps(report,indent=2,sort_keys=True))
   print(json.dumps(report,indent=2,sort_keys=True))
   return 0 if report['ready'] else 1
  elif a.command=='fetch-models':
   from floorplan_ai.model_setup import main as fetch; return fetch(['--model-dir',str(a.model_dir)]+(['--check'] if a.check else []))
  else:
   from floorplan_ai.pipeline import run_reconstruction; run_reconstruction(Path(a.input),Path(a.output))
 except (OSError,ValueError,RuntimeError) as exc: build_parser().error(str(exc))
 return 0
