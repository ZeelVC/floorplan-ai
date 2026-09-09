"""Benchmark-suite aggregation for repeated floorplan captures."""
from __future__ import annotations
from itertools import combinations
from typing import Sequence
from floorplan_ai.canonical.schema import CanonicalWorldModel

def _match_by_length(left, right):
    remaining=set(range(len(right))); pairs=[]
    for wall in sorted(left,key=lambda x:x.length):
        if not remaining: break
        i=min(remaining,key=lambda j:(abs(wall.length-right[j].length),j)); pairs.append((wall,right[i])); remaining.remove(i)
    return pairs

def repeatability(models: Sequence[CanonicalWorldModel]) -> dict:
    errors=[]
    for a,b in combinations(models,2):
        for left,right in _match_by_length(a.walls,b.walls):
            absolute=abs(left.length-right.length); errors.append((absolute,absolute/max(right.length,1e-12)))
    return {'capture_count':len(models),'comparison_count':len(errors),'mean_absolute_difference_m':sum(x[0] for x in errors)/len(errors) if errors else None,'within_1cm_rate':sum(x[0]<=.01 for x in errors)/len(errors) if errors else None,'within_0_5_percent_rate':sum(x[1]<=.005 for x in errors)/len(errors) if errors else None,'passes_repeatability_gate':bool(errors) and all(x[0]<=.01 or x[1]<=.005 for x in errors),'gate':'wall length within 1 cm or 0.5%'}

def summarize_reports(reports: Sequence[dict]) -> dict:
    def rate(name):
        values=[r.get(name,{}).get('pass_rate') for r in reports if r.get(name,{}).get('pass_rate') is not None]
        return sum(values)/len(values) if values else None
    return {'case_count':len(reports),'wall_pass_rate_mean':rate('wall_length'),'opening_pass_rate_mean':rate('opening_width'),'ceiling_pass_rate_mean':rate('ceiling_height'),'cases_with_topology_match':sum(bool(r.get('room_topology',{}).get('degree_sequence_match')) for r in reports),'cases_with_all_measurement_intervals':sum(bool(r.get('confidence',{}).get('all_measurements_with_95_interval')) for r in reports)}
