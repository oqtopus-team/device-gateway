"""Verify device-gateway's StimBackend against the 256-qubit split topology.

Exercises the real StimBackend.execute() path (qiskit QASM3 -> StimCompiler ->
stim sampling -> qulacs-ordered counts) using the generated
device_topology_sim_256.json.

Run from the repo root:
    uv run python scratch-stim256/verify_stim_256.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from device_gateway.plugins.stim.backend import StimBackend  # noqa: E402

HERE = Path(__file__).resolve().parent
TOPO = HERE / "device_topology_sim_256.json"


def make_backend() -> StimBackend:
    with tempfile.TemporaryDirectory() as d:
        status = Path(d) / "device_status"
        status.write_text("active")
        config = {
            "device_info": {"provider_id": "oqtopus", "max_shots": 10000},
            "device_status_path": str(status),
            "device_topology_json_path": str(TOPO),
        }
        return StimBackend(
            device_type="simulator",
            config=config,
            plugin_config={"supported_gates": ["x", "h", "sx", "z", "rz", "cx", "measure", "barrier", "delay"]},
        )


def check(name: str, counts: dict, expected: set[str], shots: int) -> bool:
    ok = set(counts) == expected
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {counts} (expected keys {expected})")
    # every non-zero count present, keys exactly the expected set
    return ok


def main() -> None:
    topo = json.loads(TOPO.read_text())
    assert len(topo["qubits"]) == 256, "topology must have 256 qubits"
    backend = make_backend()
    shots = 2000

    results = []

    # 1. Bell state within component 1 (qubits 0,1)
    bell = """OPENQASM 3;
include "stdgates.inc";
qubit[2] q;
bit[2] c;
h q[0];
cx q[0], q[1];
c[0] = measure q[0];
c[1] = measure q[1];
"""
    counts, msg = backend.execute(bell, shots)
    results.append(check("bell (in-component)", counts, {"00", "11"}, shots))

    # 2. Bell state across two different components (qubit 0 and qubit 80)
    cross = """OPENQASM 3;
include "stdgates.inc";
qubit[81] q;
bit[2] c;
h q[0];
cx q[0], q[80];
c[0] = measure q[0];
c[1] = measure q[80];
"""
    counts, msg = backend.execute(cross, shots)
    results.append(check("bell (cross-component q0-q80)", counts, {"00", "11"}, shots))

    # 3. Highest-index qubit (255) x-gate
    high = """OPENQASM 3;
include "stdgates.inc";
qubit[256] q;
bit[1] c;
x q[255];
c[0] = measure q[255];
"""
    counts, msg = backend.execute(high, shots)
    results.append(check("x on qubit 255", counts, {"1"}, shots))

    # 4. rz(pi/2) mapped to S, then S*S == Z (h rz(pi/2) rz(pi/2) h == x) on qubit 0
    rzs = """OPENQASM 3;
include "stdgates.inc";
qubit[1] q;
bit[1] c;
h q[0];
rz(pi/2) q[0];
rz(pi/2) q[0];
h q[0];
c[0] = measure q[0];
"""
    counts, msg = backend.execute(rzs, shots)
    results.append(check("h rz(pi/2)^2 h == x", counts, {"1"}, shots))

    # 5. Non-Clifford T gate is ignored (qubit stays |0>), job must succeed
    t = """OPENQASM 3;
include "stdgates.inc";
qubit[1] q;
bit[1] c;
t q[0];
c[0] = measure q[0];
"""
    counts, msg = backend.execute(t, shots)
    results.append(check("t gate ignored", counts, {"0"}, shots))

    ok = all(results)
    print()
    print("RESULT:", "ALL PASS" if ok else "SOME FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
