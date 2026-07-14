import json
import logging
from abc import ABCMeta, abstractmethod

logger = logging.getLogger(__name__)

# Constants
SUCCESS_MESSAGE = "job is succeeded"


class BaseBackend(metaclass=ABCMeta):
    """
    BaseBackend handles the execution of a compiled circuit on quantum hardware.
    It no longer provides gate-level operations.

    Device topology loading and caching:
        - `load_device_topology()` always reads the topology JSON file from disk and
          overwrites the cache with the result. Call it directly when fresh/live data
          is required (e.g. to reflect a calibration update just written to disk).
        - The `device_topology` property, and everything derived from it (`physical_map`,
          `qubits`, `couplings`, `physical_index_to_physical_label`, etc.), returns the
          cached value and only reads from disk on first access.
    """

    def __init__(
        self, device_type: str, config: dict, plugin_config: dict | None = None
    ):
        """
        Initialize the backend with the configuration.
        This is done once at server startup.

        Args:
            device_type: The device type ("simulator" or "QPU").
            config: Settings shared across all backends (device_info, device_status_path,
                device_topology_json_path, ...).
            plugin_config: Settings specific to this backend.
        """
        self.device_type = device_type
        self.config = config
        self.plugin_config = plugin_config or {}
        self._device_topology_cache: dict | None = None

    def load_device_topology(self) -> dict:
        """
        Load the device topology from a JSON file, refreshing the cache
        used by the device_topology property.
        """
        with open(self.config["device_topology_json_path"]) as f:
            device_topology = json.load(f)
        self._device_topology_cache = device_topology
        return device_topology

    def load_device_status(self):
        """
        Load the device status from the device_status file.
        """
        with open(self.config["device_status_path"]) as f:
            device_status = f.read().strip()
        return device_status

    def save_device_topology(self, device_topology):
        with open(self.config["device_topology_json_path"], "w") as f:
            json.dump(device_topology, f, indent=4)

    def is_active(self) -> bool:
        """
        Check if the device is active.
        """
        return self.device_status == "active"

    def is_inactive(self) -> bool:
        """
        Check if the device is inactive.
        """
        return self.device_status == "inactive"

    def is_maintenance(self) -> bool:
        """
        Check if the device is in maintenance.
        """
        return self.device_status == "maintenance"

    def is_simulator(self) -> bool:
        """
        Check if the device is a simulator.
        """
        return self.device_type == "simulator"

    def is_qpu(self) -> bool:
        """
        Check if the device is a QPU.
        """
        return self.device_type == "QPU"

    @property
    def device_topology(self) -> dict:
        """
        Returns the cached device topology, loading it on first access.
        e.g., {"qubits": [{"id": 0, "physical_id": 5}], "couplings": [{"control": 0, "target": 1}]}
        Call load_device_topology() directly to force a fresh read from disk.
        """
        if self._device_topology_cache is None:
            return self.load_device_topology()
        return self._device_topology_cache

    @property
    def physical_ids(self) -> list:
        """
        Returns a list of physical IDs of the qubits, e.g., [5, 7]
        """
        return [qubit["physical_id"] for qubit in self.device_topology["qubits"]]

    @property
    def device_status(self) -> dict:
        """
        Returns the device status, e.g., "active", "inactive", "maintenance"
        """
        return self.load_device_status()

    @property
    def device_info(self) -> dict:
        """
        Returns the device information, e.g., {"device_id": "QPU1", "type": "QPU"}
        """
        info = dict(self.config["device_info"])
        info["type"] = "simulator" if self.is_simulator() else "QPU"

        # Load topology once when either field needs a fallback value
        if info.get("device_id") is None or info.get("max_qubits") is None:
            topology = self.load_device_topology()
            if info.get("device_id") is None:
                if "device_id" not in topology:
                    raise ValueError(
                        "device_id is not set in config and not found in topology"
                    )
                info["device_id"] = topology["device_id"]
            if info.get("max_qubits") is None:
                if "qubits" not in topology:
                    raise ValueError(
                        "max_qubits is not set in config and qubits not found in topology"
                    )
                info["max_qubits"] = len(topology["qubits"])

        return info

    @property
    def physical_map(self):
        """
        Returns the physical index to physical label mapping.
        The mapping is in the format physical_map: {'qubits': {0: 'Q29', 1: 'Q30', 2: 'Q31'}, 'couplings': {(2, 0): ('Q31', 'Q29'), (2, 1): ('Q31', 'Q30')}}"}
        """
        device_topology = self.device_topology
        qubits = {
            qubit["id"]: f"Q{qubit['physical_id']:02}"
            for qubit in device_topology["qubits"]
        }
        couplings = {
            (c["control"], c["target"]): (
                qubits[c["control"]],
                qubits[c["target"]],
            )
            for c in device_topology["couplings"]
        }
        return {"qubits": qubits, "couplings": couplings}

    @property
    def qubits(self) -> list:
        """
        Returns a list of qubit labels, e.g., ["Q05", "Q07"]
        """
        return list(self.physical_map["qubits"].values())  # type: ignore

    @property
    def couplings(self) -> list:
        """
        Returns a list of couplings in the format "QXX-QYY", e.g., ["Q05-Q07", "Q07-Q05"]
        """
        return [
            f"{v[0]}-{v[1]}"
            for v in self.physical_map["couplings"].values()  # type: ignore
        ]  # type: ignore

    @property
    def physical_index_to_physical_label(self) -> dict:
        """
        Returns the physical index to physical label mapping, e.g., {0: "Q05", 1: "Q07"}
        """
        # Return a shallow copy to avoid accidental modifications
        return self.physical_map["qubits"].copy()  # type: ignore

    @property
    def physical_label_to_physical_index(self) -> dict:
        """
        Returns the physical label to physical index mapping, e.g., {"Q05": 0, "Q07": 1}
        """
        return {v: k for k, v in self.physical_index_to_physical_label.items()}

    def physical_label(self, physical_index: str) -> str:
        """
        Returns the physical label corresponding to the physical index.
        """
        return self.physical_index_to_physical_label[physical_index]

    def physical_index(self, physical_label: str) -> int:
        """
        Returns the physical index corresponding to the physical label.
        """
        return self.physical_label_to_physical_index[physical_label]

    @abstractmethod
    def execute(self, program: str, shots: int = 1024) -> tuple[dict, str]:
        """Parse, compile, execute, and format the results of the given program.

        This method should be implemented in the derived class. It is fully
        responsible for parsing the program, compiling it to the backend's
        native representation, executing it, and returning the measurement
        counts with zero-count entries removed.

        Args:
            program: The circuit to be executed.
            shots: The number of shots to execute the circuit.
        Returns:
            A tuple containing the counts of measurement results and a success message.
            The counts are in the format {"000": 512, "111": 512}.

        """
        pass
