import argparse
import json
import logging
import logging.config
import time
from concurrent import futures
from pathlib import Path

import grpc
import yaml  # type: ignore[import]
from grpc_reflection.v1alpha import reflection
from qiskit.qasm3 import loads
from qpu_interface.v1 import qpu_pb2, qpu_pb2_grpc

from device_gateway.backend.qulacs_backend import QulacsBackend
from device_gateway.circuit.qulacs_circuit import QulacsCircuit

logger = logging.getLogger("device_gateway")


class ServerImpl(qpu_pb2_grpc.QpuServiceServicer):
    def __init__(self, config: dict):
        super().__init__()
        self._config = config
        if self._config["simulator_mode"]:
            self._qulacs = QulacsBackend(self.virtual_physical_map)
        else:
            raise NotImplementedError("Qubex is not implemented yet.")

    @property
    def device_topology_json(self):
        with open(self._config["device_topology_json_path"]) as f:
            device_topology = json.load(f)
        return device_topology

    @property
    def device_status(self):
        return self._config["device_status"]

    @property
    def virtual_physical_map(self):
        device_topology = self.device_topology_json
        qubits = {
            qubit["id"]: qubit["physical_id"] for qubit in device_topology["qubits"]
        }
        couplings = {
            (c["control"], c["target"]): (qubits[c["control"]], qubits[c["target"]])
            for c in device_topology["couplings"]
        }
        return {"qubits": qubits, "couplings": couplings}

    def CallJob(self, request: qpu_pb2.CallJobRequest, context):  # type: ignore[name-defined]
        try:
            start_time = time.time()
            job_id = request.job_id
            logger.info(f"CallJob is started. job_id={job_id}")
            simulator_mode = self._config["simulator_mode"]
            print("virtual_physical_map", self.virtual_physical_map)
            qc = loads(request.program)
            if simulator_mode:
                qulacs_circuit = QulacsCircuit(self._qulacs).compile(qc)
                counts = self._qulacs.execute(qulacs_circuit, shots=request.shots)
            else:
                raise NotImplementedError("Qubex is not implemented yet.")
            message = "job is succeeded"
            result = qpu_pb2.Result(counts=counts, message=message)  # type: ignore[attr-defined]
            response = qpu_pb2.CallJobResponse(  # type: ignore[attr-defined]
                status=qpu_pb2.JobStatus.JOB_STATUS_SUCCESS,  # type: ignore[attr-defined]
                result=result,
            )
        except Exception:
            logger.error(
                f"CallJob. job_id={job_id}, Exception occurred.",
                exc_info=True,
            )
            result = qpu_pb2.Result(message="internal server error")  # type: ignore[attr-defined]
            response = qpu_pb2.CallJobResponse(  # type: ignore[attr-defined]
                status=qpu_pb2.JobStatus.JOB_STATUS_FAILURE,  # type: ignore[attr-defined]
                result=result,
            )
        finally:
            elapsed_time = time.time() - start_time
            logger.info(
                f"CallJob is finished. elapsed_time_sec={elapsed_time:.3f}, job_id={job_id}, status={response.status}"
            )
            return response

    def GetServiceStatus(self, request, context):
        try:
            logger.info("GetServiceStatus is started.")
            if self.device_status == "active":
                service_status = qpu_pb2.ServiceStatus.SERVICE_STATUS_ACTIVE
            elif self.device_status == "inactive":
                service_status = qpu_pb2.ServiceStatus.SERVICE_STATUS_INACTIVE
            elif self.device_status == "maintenance":
                service_status = qpu_pb2.ServiceStatus.SERVICE_STATUS_MAINTENANCE
            else:
                msg = f"service status '{self._status}' is not supported."
                raise ValueError(msg)

            # build response parameters
            response_parameters = {
                "service_status": service_status,
                "device_info_timestamp": self.device_topology_json["timestamp"],
            }
            response = qpu_pb2.GetServiceStatusResponse(**response_parameters)
        except Exception:
            logger.error("GetServiceStatus. Exception occurred.", exc_info=True)
            response = qpu_pb2.GetServiceStatusResponse(
                service_status=qpu_pb2.ServiceStatus.SERVICE_STATUS_INACTIVE
            )

        finally:
            logger.info(f"GetServiceStatus is finished. response={response_parameters}")
            return response

    def GetDeviceInfo(self, request: qpu_pb2.GetDeviceInfoRequest, context):  # type: ignore[name-defined]
        try:
            logger.info("GetDeviceInfo is started.")
            response_parameters = self._config["device_info"]
            response_parameters["device_info"] = json.dumps(self.device_topology_json)
            device_info = qpu_pb2.DeviceInfo(**response_parameters)  # type: ignore[attr-defined]
            response = qpu_pb2.GetDeviceInfoResponse(  # type: ignore[attr-defined]
                body=device_info
            )
        except Exception:
            logger.error("GetDeviceInfo. Exception occurred.", exc_info=True)
            response = qpu_pb2.GetDeviceInfoResponse()  # type: ignore[attr-defined]
        finally:
            logger.info("GetDeviceInfo is finished.")
            return response


def serve(config_yaml_path: str, logging_yaml_path: str):
    with Path(config_yaml_path).open("r", encoding="utf-8") as file:
        config_yaml = yaml.safe_load(file)
    with Path(logging_yaml_path).open("r", encoding="utf-8") as file:
        logging_yaml = yaml.safe_load(file)
        logging.config.dictConfig(logging_yaml)

    max_workers = config_yaml["proto"].get("max_workers", 10)
    address = config_yaml["proto"].get("address", "[::]:50051")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    qpu_pb2_grpc.add_QpuServiceServicer_to_server(
        ServerImpl(config=config_yaml), server
    )
    service_names = (
        qpu_pb2.DESCRIPTOR.services_by_name["QpuService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)
    server.add_insecure_port(address)
    logger.info(f"Started device gateway. address={address}")

    server.start()
    server.wait_for_termination()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the gRPC server with configuration files."
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to the server configuration file (YAML format).",
    )
    parser.add_argument(
        "-l",
        "--logging",
        type=str,
        default="config/logging.yaml",
        help="Path to the logging configuration file (YAML format).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    serve(args.config, args.logging)
