from floorplan_ai.evaluation.benchmark import repeatability, summarize_reports

def test_repeatability_empty_and_report_summary():
    assert repeatability([])["passes_repeatability_gate"] is False
    report = summarize_reports([{"wall_length":{"pass_rate":1.0},"opening_width":{"pass_rate":0.5},"ceiling_height":{"pass_rate":1.0},"room_topology":{"degree_sequence_match":True},"confidence":{"all_measurements_with_95_interval":True}}])
    assert report["case_count"] == 1
    assert report["wall_pass_rate_mean"] == 1.0
    assert report["cases_with_topology_match"] == 1
