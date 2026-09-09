"""Generate a 256-qubit simulator topology split into multiple disconnected graphs.

The gateway reads a device topology JSON with the following shape:
    {
      "name": str, "device_id": str,
      "qubits": [{id, physical_id, position{x,y}, fidelity, meas_error{...},
                  qubit_lifetime{t1,t2}, gate_duration{rz,sx,x}}],
      "couplings": [{control, target, fidelity, gate_duration{rzx90}}],
      "calibrated_at": str
    }

- `id` is the logical index (0..255); the stim compiler maps a qiskit qubit's
  logical index to a physical label via `physical_index_to_physical_label[id]`.
- `physical_id` is used for the physical label "Q{physical_id:02}".
- `couplings` reference qubits by `id`. Couplings are only added inside each
  component, so the graph is deliberately split into several disconnected
  components.

Run:  python3 generate_topology_256.py
Output: device_topology_sim_256.json
"""
import json
import math
from datetime import datetime, timezone

# Component sizes must sum to 256.
COMPONENT_SIZES = [80, 60, 40, 30, 20, 15, 8, 3]
GAP = 4  # spacing between component bounding boxes (in coordinate units)

TOTAL = sum(COMPONENT_SIZES)


def component_edges(ids: list[int], width: int) -> list[tuple[int, int]]:
    """Return grid edges (right + down neighbors) among the given node ids."""
    idset = set(ids)
    edges = []
    for i in ids:
        row = i // width
        col = i % width
        right = i + 1
        if right in idset and right // width == row:
            edges.append((i, right))
        down = i + width
        if down in idset:
            edges.append((i, down))
    return edges


def build_topology() -> dict:
    qubits = []
    couplings = []

    next_id = 0  # logical id, sequential 0..255
    y_offset = 0.0  # each component sits in its own horizontal band

    for size in COMPONENT_SIZES:
        width = math.ceil(math.sqrt(size))
        ids = list(range(next_id, next_id + size))
        height = math.ceil(size / width)

        for within, local in enumerate(ids):
            qubits.append(
                {
                    "id": local,
                    "physical_id": local,  # label becomes Q{id:02}
                    "position": {
                        "x": float(within % width),
                        "y": float(y_offset + (within // width)),
                    },
                    "fidelity": 0.999,
                    "meas_error": {
                        "prob_meas1_prep0": 0.001,
                        "prob_meas0_prep1": 0.001,
                        "readout_assignment_error": 0.001,
                    },
                    "qubit_lifetime": {"t1": 100.0, "t2": 100.0},
                    "gate_duration": {"rz": 20, "sx": 20, "x": 20},
                }
            )

        for a, b in component_edges(ids, width):
            couplings.append(
                {
                    "control": a,
                    "target": b,
                    "fidelity": 0.99,
                    "gate_duration": {"rzx90": 20},
                }
            )

        next_id += size
        y_offset += height + GAP

    assert next_id == TOTAL, f"expected {TOTAL} qubits, got {next_id}"

    return {
        "name": "stim-sim-256",
        "device_id": "stim",
        "qubits": qubits,
        "couplings": couplings,
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    topo = build_topology()
    out = "device_topology_sim_256.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(topo, f, indent=4)
    print(f"wrote {out}: {len(topo['qubits'])} qubits, {len(topo['couplings'])} couplings")


if __name__ == "__main__":
    main()
