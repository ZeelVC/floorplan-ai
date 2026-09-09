from floorplan_ai.video.trajectory import DriftDiagnostics
def test_drift_diagnostics_does_not_claim_correction():
 assert not DriftDiagnostics(False,0.,(),0.).estimated
