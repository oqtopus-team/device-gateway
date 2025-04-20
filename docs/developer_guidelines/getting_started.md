# Getting Started

## Runging the server locally

```bash
mkdir logs
make run
```

## Running the server in a container

```bash
docker compose up
```

## List all services

```bash
grpcurl -plaintext "[::]:51021" list
```

## List all methods of a service

```bash
grpcurl -plaintext "[::]:51021" list qpu_interface.v1.QpuService
```

## Get service status

```bash
grpcurl -plaintext "[::]:51021" qpu_interface.v1.QpuService.GetServiceStatus
```

## Job Request

```bash
grpcurl -plaintext -d '{ "job_id": "test_job", "shots": 1000, "program": "OPENQASM 3;include \"stdgates.inc\";qubit[2] q;bit[2] c;rz(1.5707963267948932) q[0];sx q[0];rz(1.5707963267948966) q[0];cx q[0], q[1];c[0] = measure q[0];c[1] = measure q[1];" }' "[::]:51021" qpu_interface.v1.QpuService.CallJob
```

## Device info request

```bash
grpcurl -plaintext "[::]:51021" qpu_interface.v1.QpuService.GetDeviceInfo
```

## Generate device info

```bash
uv run src/device_gateway/tool/device_info_generator.py -c config/config.yaml
```

## Qubex Integration

if you use QDash, please download the Qubex config file and generate the device topology.

### Download Qubex Config

```bash
make download-qubex-config
```

### Generate Device Topology

```bash
make generate-device-topology
```


## Configuration

### Configuration File
The configuration file is located at `config/config.yaml`. The configuration file is in YAML format and contains the following sections:

- `proto`: The gRPC server configuration.
  - `max_workers`: The maximum number of workers for the gRPC server.
  - `address`: The address of the gRPC server.
- `device_info`: The device information.
  - `device_id`: The ID of the device.
  - `provider_id`: The ID of the provider.
  - `max_qubits`: The maximum number of qubits supported by the device.
  - `max_shots`: The maximum number of shots supported by the device.
- `simulator_mode`: Whether to run the server in simulator mode or not.
- `device_status`: The status of the device. Can be `active`, `inactive` or `maintenance`.
- `device_topology_json_path`: The path to the device topology JSON file.


### Simulator Example

```yaml
proto:
  max_workers: 2
  address: "[::]:51021"
device_info:
  device_id: "qulacs"
  provider_id: "oqtopus"
  max_qubits: 3
  max_shots: 10000
simulator_mode: true
device_status: active
device_topology_json_path: config/device_topology_sim.json
```

### QPU Example

```yaml
proto:
  max_workers: 2
  address: "[::]:51021"
device_info:	
  device_id: "anemone"
  provider_id: "oqtopus"
  max_qubits: 3
  max_shots: 10000
simulator_mode: false
device_status: active
device_topology_json_path: config/device_topology.json
```
