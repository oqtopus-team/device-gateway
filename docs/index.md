![OQTOPUS](./image/oqtopus_logo.png)

# device-gateway

The device-gateway is a server that translates OpenQASM3 instructions into commands compatible with various quantum control software platforms. It maintains calibration data and device topology information, enabling the mapping of virtual qubits specified in the OpenQASM code to physical qubits during the pulse generation process. The system employs gRPC for efficient remote procedure calls. Its modular backend architecture supports integration with diverse quantum control software and simulators, with the current implementation utilizing Qulacs as the simulator backend. Moreover, the device-gateway operates in close collaboration with the oqtopus-engine.

## Getting Started

### Local Development

```bash
git clone https://github.com/oqtopus-team/device-gateway.git
```

```bash
uv sync
```

### Runging the server locally

```bash
mkdir logs
make run
```

### Running the server in a container

```bash
docker compose up
```

## List all services

```bash
grpcurl -plaintext "[::]:50051" list
```

## List all methods of a service

```bash
grpcurl -plaintext "[::]:50051" list qpu_interface.v1.QpuService
```

## Get service status

```bash
grpcurl -plaintext "[::]:50051" qpu_interface.v1.QpuService.GetServiceStatus
```

## Job Request

```bash
grpcurl -plaintext -d '{ "job_id": "test_job", "shots": 1000, "program": "OPENQASM 3;include \"stdgates.inc\";qubit[2] q;bit[2] c;rz(1.5707963267948932) q[0];sx q[0];rz(1.5707963267948966) q[0];cx q[0], q[1];c[0] = measure q[0];c[1] = measure q[1];" }' "[::]:50051" qpu_interface.v1.QpuService.CallJob
```

## Device info request

```bash
grpcurl -plaintext "[::]:50051" qpu_interface.v1.QpuService.GetDeviceInfo
```

## Generate device info

```bash
uv run src/device_gateway/tool/device_info_generator.py --device-id 1 \
    --qubit-index-list "5,7" \
    --system-note-file data/.system_note.json \
    --output-json config/_device_topology.json \
    --output-png config/_device_topology.png \
    --save
```
