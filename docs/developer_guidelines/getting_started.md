# Getting Started

## Generate config files

```bash
make generate-config
```

## Locally run the server

```bash
uv sync --no-group qubex --no-dev
```

and then run the server:

```bash
make run
```

## Running the server in a container

```bash
docker compose up device-gateway
```

## Change Device Status

### Change the device status "active"

```bash
make change-status-to-active
```

### Change the device status "inactive"

```bash
make change-status-to-inactive
```

### Change the device status "maintenance"

```bash
make change-status-to-maintenance
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

### Running the Qubex server in a container

```bash
docker compose up device-gateway-qubex
```

## Development

### Format code

```bash
make format
```

### Run linting

```bash
make lint
```

### Run tests

```bash
make test
```

### Run all verification steps

```bash
make verify
```

## Documentation

### Lint documentation

```bash
make docs-lint
```

### Build documentation

```bash
make docs-build
```

### Serve documentation locally

```bash
make docs-serve
```

## Backend Plugins

Device Gateway executes circuits through pluggable backends. A backend can be any importable Python class,
instantiated by the `_target_` fully-qualified class path declared in `backend_di_container.registry` in
`config.yaml`. The DI container (from [oqtopus-util](https://oqtopus-util.readthedocs.io/)) simply imports and
constructs whatever class `_target_` points to.

A backend is a class that subclasses `device_gateway.core.base_backend.BaseBackend` and implements a single
required method:

```python
def execute(self, program: str, shots: int = 1024) -> tuple[dict, str]:
    ...
```

`execute()` is fully responsible for parsing the incoming program, compiling it to the backend's native
representation, running it, and returning `(counts, message)`. `BaseBackend` itself only provides shared,
backend-agnostic functionality (device topology/status loading, qubit label <-> index mapping, gate-name
validation via the optional `supported_gates` config key); it does not prescribe how a backend parses programs
or represents circuits internally.

### Backends included with this repository

| Backend | `_target_`                                            | Device type | Notes                                                                     |
| ------- | ----------------------------------------------------- | ----------- | ------------------------------------------------------------------------- |
| Qulacs  | `device_gateway.plugins.qulacs.backend.QulacsBackend` | `simulator` | State-vector simulator.                                                   |
| Qubex   | `device_gateway.plugins.qubex.backend.QubexBackend`   | `QPU`       | Controls real superconducting hardware via the `qubex` library.           |

## Configuration

### Configuration File

The configuration file is located at `config/config.yaml`.

The configuration file is loaded using [oqtopus-util](https://oqtopus-util.readthedocs.io/), which supports environment variable substitution with optional default values
using the `${VAR, default}` syntax. If the environment variable is not set, the default value is used.

Backends are managed by [oqtopus-util's DiContainer](https://oqtopus-util.readthedocs.io/).
The `backend_di_container` configuration follows the DiContainer syntax defined by oqtopus-util.

The configuration file contains the following sections:

- `proto`: The gRPC settings.
  - `max_workers`: The maximum number of workers for the gRPC server.
  - `address`: The address of the gRPC server.
- `common_backend_settings`: Common settings shared across all backends.
  - `device_info`: The device information.
    - `device_id`: The ID of the device. If omitted, derived from the device topology file.
    - `provider_id`: The ID of the provider.
    - `max_qubits`: The maximum number of qubits supported by the device. If omitted, derived from the device topology file.
    - `max_shots`: The maximum number of shots supported by the device.
  - `device_status_path`: The path to the device status file.
  - `device_topology_json_path`: The path to the device topology JSON file.
  - `supported_gates`: The list of OpenQASM3 instruction names the backend's compiler is allowed to execute (e.g. `[x, sx, rz, cx, measure, barrier, delay]`). Optional — comment it out to disable gate-name validation entirely and allow any instruction the compiler recognizes.
- `default_backend`: The backend to use. Available options are `"qulacs"` and `"qubex"`. Required.
- `backend_di_container`: The dependency injection container configuration for backends.
  - `registry`: The registry of available backends. Each entry has the following fields:
    - `_target_`: The fully qualified class name of the backend.
    - `device_type`: The device type (`"simulator"` or `"QPU"`).
    - `config`: The backend configuration (reference to `common_backend_settings`).
  - Only the backend specified by `default_backend` is instantiated. Other entries in `registry` are ignored. For example, if `default_backend: qulacs`, a `qubex` entry in `registry` will not be loaded.

### Simulator Example

```yaml
# gRPC settings
proto:
  max_workers: 2
  address: "localhost:51021"

# Common backend settings
common_backend_settings: &common_backend_settings
  device_info:
    # device_id: "qulacs"
    provider_id: "oqtopus"
    # max_qubits: 16
    max_shots: 10000
  device_status_path: config/device_status
  device_topology_json_path: config/device_topology_sim.json
  # Comment out supported_gates below to disable gate-name validation entirely.
  supported_gates: [x, sx, rz, cx, measure, barrier, delay]

# Backend configuration
default_backend: qulacs  # Available options: "qulacs", "qubex"

# Dependency Injection Container Configuration
backend_di_container:
  registry:
    # QulacsBackend settings
    qulacs:
      _target_: device_gateway.plugins.qulacs.backend.QulacsBackend
      device_type: simulator
      config: *common_backend_settings
    # QubexBackend settings
    qubex:
      _target_: device_gateway.plugins.qubex.backend.QubexBackend
      device_type: QPU
      config: *common_backend_settings
      qubex_config:
        chip_id: ${CHIP_ID, 64Q}
        config_dir: ${CONFIG_DIR, "/app/qubex-config/{chip_id}/config"}
        params_dir: ${PARAMS_DIR, "/app/qubex-config/{chip_id}/params"}
        calib_note_path: ${CALIB_NOTE_PATH, "/app/qubex-config/{chip_id}/calibration/calib_note.json"}
```

### QPU Example

```yaml
# gRPC settings
proto:
  max_workers: 2
  address: "localhost:51021"

# Common backend settings
common_backend_settings: &common_backend_settings
  device_info:
    # device_id: "qulacs"
    provider_id: "oqtopus"
    # max_qubits: 16
    max_shots: 10000
  device_status_path: config/device_status
  device_topology_json_path: config/device_topology_sim.json
  # Comment out supported_gates below to disable gate-name validation entirely.
  supported_gates: [x, sx, rz, cx, measure, barrier, delay]

# Backend configuration
default_backend: qubex  # Available options: "qulacs", "qubex"

# Dependency Injection Container Configuration
backend_di_container:
  registry:
    # QulacsBackend settings
    qulacs:
      _target_: device_gateway.plugins.qulacs.backend.QulacsBackend
      device_type: simulator
      config: *common_backend_settings
    # QubexBackend settings
    qubex:
      _target_: device_gateway.plugins.qubex.backend.QubexBackend
      device_type: QPU
      config: *common_backend_settings
      qubex_config:
        chip_id: ${CHIP_ID, 64Q}
        config_dir: ${CONFIG_DIR, "/app/qubex-config/{chip_id}/config"}
        params_dir: ${PARAMS_DIR, "/app/qubex-config/{chip_id}/params"}
        calib_note_path: ${CALIB_NOTE_PATH, "/app/qubex-config/{chip_id}/calibration/calib_note.json"}
```
