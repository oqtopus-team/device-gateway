"""gRPC client to verify the running device-gateway (stim backend, 256-qubit topology).

Run from the repo root:
    uv run python scratch-stim256/grpc_client.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import grpc  # noqa: E402
from device_gateway.gen.qpu.v1 import qpu_pb2, qpu_pb2_grpc  # noqa: E402


def main() -> None:
    channel = grpc.insecure_channel("localhost:51021")
    stub = qpu_pb2_grpc.QpuServiceStub(channel)

    # Device info: confirm max_qubits == 256
    info = stub.GetDeviceInfo(qpu_pb2.GetDeviceInfoRequest())
    body = info.body
    print(f"GetDeviceInfo: device_id={body.device_id} type={body.type} "
          f"max_qubits={body.max_qubits} max_shots={body.max_shots}")
    assert body.max_qubits == 256, "expected max_qubits 256"

    jobs = [
        ("bell-in-component", """OPENQASM 3;
include "stdgates.inc";
qubit[2] q; bit[2] c;
h q[0]; cx q[0], q[1];
c[0] = measure q[0]; c[1] = measure q[1];
"""),
        ("bell-cross-component", """OPENQASM 3;
include "stdgates.inc";
qubit[81] q; bit[2] c;
h q[0]; cx q[0], q[80];
c[0] = measure q[0]; c[1] = measure q[80];
"""),
        ("x-qubit-255", """OPENQASM 3;
include "stdgates.inc";
qubit[256] q; bit[1] c;
x q[255]; c[0] = measure q[255];
"""),
        ("rz-pi2-x", """OPENQASM 3;
include "stdgates.inc";
qubit[1] q; bit[1] c;
h q[0]; rz(pi/2) q[0]; rz(pi/2) q[0]; h q[0];
c[0] = measure q[0];
"""),
        ("t-ignored", """OPENQASM 3;
include "stdgates.inc";
qubit[1] q; bit[1] c;
t q[0]; c[0] = measure q[0];
"""),
    ]

    all_ok = True
    for name, program in jobs:
        resp = stub.CallJob(qpu_pb2.CallJobRequest(job_id=f"stim256-{name}", shots=2000, program=program))
        counts = dict(resp.result.counts)
        ok = resp.status == qpu_pb2.JOB_STATUS_SUCCESS
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: status={resp.status} counts={counts}")
        all_ok = all_ok and ok

    print()
    print("RESULT:", "ALL PASS" if all_ok else "SOME FAILED")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
