import argparse
import json
import logging
import logging.config
import os
import time
from concurrent import futures
from pathlib import Path

import grpc
import yaml  # type: ignore[import]
from grpc_reflection.v1alpha import reflection

from device_gateway.core.plugin_manager import (
    SUPPORTED_BACKENDS,
    BackendPluginManager,
)
from device_gateway.gen.qpu.v1 import qpu_pb2, qpu_pb2_grpc

logger = logging.getLogger("device_gateway")


# Constants
DEFAULT_BACKEND = "qulacs"
ERROR_UNSUPPORTED_BACKEND = "Backend '{}' is specified but not supported."
ERROR_DEVICE_INACTIVE = "device is inactive"
ERROR_INTERNAL_SERVER = "internal server error"
ERROR_UNSUPPORTED_STATUS = "Service status '{}' is not supported."
SUCCESS_MESSAGE = "job is succeeded"


class ServerImpl(qpu_pb2_grpc.QpuServiceServicer):
    def __init__(
        self,
        config: dict,
    ):
        """Initialize the QPU service.

        Args:
            config: Configuration dictionary.
        """
        super().__init__()
        self._backend_manager = BackendPluginManager()
        self._initialize_backend(config)
        logger.info(f"ServerImpl initialized with backend: {self.backend_name}")
        logger.info(f"device_info={self.backend.device_info}")
        logger.info(f"device_topology={self.backend.device_topology}")
        logger.info(f"device_status={self.backend.device_status}")

    def _load_plugin(self, plugin_config: dict) -> None:
        """Load a plugin's backend and circuit components.

        Args:
            plugin_config: Plugin configuration dictionary

        Raises:
            ImportError: If the specified plugin is not supported.
        """
        name = plugin_config.get("name")
        if name not in SUPPORTED_BACKENDS:
            logger.error(ERROR_UNSUPPORTED_BACKEND.format(plugin_config))
            raise ImportError(ERROR_UNSUPPORTED_BACKEND.format(plugin_config))

        try:
            self._backend_manager.load_backend(config={"plugin": plugin_config})
        except ImportError as e:
            logger.error(f"Failed to load plugin {name}: {str(e)}")
            raise

    def _initialize_backend(self, config: dict) -> None:
        """Initialize backend with configuration.

        Args:
            config: Configuration dictionary.
        """
        plugin_config = config.get("plugin", {"name": DEFAULT_BACKEND})
        self.backend_name = plugin_config.get("name", DEFAULT_BACKEND)
        self._load_plugin(plugin_config)
        self.backend = self._backend_manager.get_backend(self.backend_name, config)

    def _create_error_response(self, message: str) -> qpu_pb2.CallJobResponse:
        """Create error response with the given message.

        Args:
            message: Error message.

        Returns:
            CallJobResponse with error status.
        """
        result = qpu_pb2.Result(message=message)  # type: ignore[attr-defined]
        return qpu_pb2.CallJobResponse(  # type: ignore[attr-defined]
            status=qpu_pb2.JobStatus.JOB_STATUS_FAILURE,  # type: ignore[attr-defined]
            result=result,
        )

    def _remove_zero_values(self, d: dict[str, int]) -> dict[str, int]:
        """remove zero values from a dictionary.
        Args:
            d: Dictionary with string keys and integer values.
        Returns:
            Dictionary with zero values removed.
        """
        return {k: v for k, v in d.items() if v != 0}

    def CallJob(self, request: qpu_pb2.CallJobRequest, context):  # type: ignore[name-defined]
        """Execute quantum job and return results.

        Args:
            request: Job request containing program and shots.
            context: gRPC context.

        Returns:
            CallJobResponse containing execution results or error.
        """
        start_time = time.time()
        job_id = request.job_id
        logger.info(f"CallJob is started. job_id={job_id}")

        try:
            if self.backend.is_inactive():
                logger.error(
                    f"CallJob. job_id={job_id}, device is inactive. "
                    "Please check the device status."
                )
                return self._create_error_response(ERROR_DEVICE_INACTIVE)

            logger.info(f"program={request.program}, shots={request.shots}")
            counts, message = self.backend.execute(request.program, shots=request.shots)
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
            response = self._create_error_response(ERROR_INTERNAL_SERVER)

        finally:
            elapsed_time = time.time() - start_time
            logger.info(
                f"CallJob is finished. elapsed_time_sec={elapsed_time:.3f}, job_id={job_id}, status={response.status}"
            )
            return response

    def _get_service_status(self) -> qpu_pb2.ServiceStatus:
        """Get current service status.

        Returns:
            ServiceStatus enum value.

        Raises:
            ValueError: If the service status is not supported.
        """
        if self.backend.is_active():
            return qpu_pb2.ServiceStatus.SERVICE_STATUS_ACTIVE
        elif self.backend.is_inactive():
            return qpu_pb2.ServiceStatus.SERVICE_STATUS_INACTIVE
        elif self.backend.is_maintenance():
            return qpu_pb2.ServiceStatus.SERVICE_STATUS_MAINTENANCE
        else:
            raise ValueError(ERROR_UNSUPPORTED_STATUS.format(self.device_status))

    def GetServiceStatus(self, request, context):
        """Get current service status.

        Args:
            request: Service status request.
            context: gRPC context.

        Returns:
            GetServiceStatusResponse containing current service status.
        """
        try:
            logger.info("GetServiceStatus is started.")
            service_status = self._get_service_status()
            response_parameters = {"service_status": service_status}
            response = qpu_pb2.GetServiceStatusResponse(**response_parameters)

        except Exception:
            logger.error("GetServiceStatus. Exception occurred.", exc_info=True)
            response_parameters = {
                "service_status": qpu_pb2.ServiceStatus.SERVICE_STATUS_INACTIVE
            }
            response = qpu_pb2.GetServiceStatusResponse(**response_parameters)

        finally:
            logger.info(f"GetServiceStatus is finished. response={response_parameters}")
            return response

    def _get_device_info_parameters(self) -> dict:
        """Get device information parameters.

        Returns:
            Dictionary containing device information parameters.
        """
        parameters = self.backend.device_info.copy()
        parameters["device_info"] = json.dumps(self.backend.device_topology)
        parameters["calibrated_at"] = self.backend.device_topology["calibrated_at"]
        return parameters

    def GetDeviceInfo(self, request: qpu_pb2.GetDeviceInfoRequest, context):  # type: ignore[name-defined]
        """Get device information.

        Args:
            request: Device info request.
            context: gRPC context.

        Returns:
            GetDeviceInfoResponse containing device information.
        """
        try:
            logger.info("GetDeviceInfo is started.")
            response_parameters = self._get_device_info_parameters()
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


def assign_environ(config: dict) -> dict:
    """Expand environment variables and the user directory "~" in the values of `dict`.

    Args:
        config (dict): `dict` that expands environment variables
            and the user directory "~" in its values.

    Returns:
        dict: expanded `dict`.

    """
    for key, value in config.items():
        if type(value) is dict:
            config[key] = assign_environ(value)
        elif type(value) is str:
            tmp_value = str(os.path.expandvars(value))
            config[key] = os.path.expanduser(tmp_value)  # noqa: PTH111
    return config


def serve(config_yaml_path: str, logging_yaml_path: str):
    with Path(config_yaml_path).open("r", encoding="utf-8") as file:
        config_yaml = assign_environ(yaml.safe_load(file))
    with Path(logging_yaml_path).open("r", encoding="utf-8") as file:
        logging_yaml = assign_environ(yaml.safe_load(file))
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
