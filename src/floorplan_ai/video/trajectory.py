from dataclasses import dataclass
@dataclass(frozen=True)
class DriftDiagnostics: estimated:bool; confidence:float; loop_candidates:tuple[str,...]; trajectory_length:float
