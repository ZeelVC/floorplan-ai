# Offline runtime

`reconstruct` performs no model acquisition and has no cloud API path. The optional Apple Depth Pro adapter requires an explicitly local checkpoint and fails with `floorplan-ai fetch-models` guidance when absent. The manifest records source and expected location; weights are not committed.
