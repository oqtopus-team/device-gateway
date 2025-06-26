import json
import logging
from abc import ABCMeta, abstractmethod
from typing import Any

from qiskit.qasm3 import loads

logger = logging.getLogger("device_gateway")

# Constants
SUCCESS_MESSAGE = "job is succeeded"


class BaseBackend(metaclass=ABCMeta):
    """
    BaseBackend handles the execution of a compiled circuit on quantum hardware.
    It no longer provides gate-level operations.
    """

    def __init__(self, config: dict):
        """
        Initialize the backend with the configuration.
        This is done once at server startup.
        """
        self.config = config

    def load_device_topology(self):
        """
        Load the device topology from a JSON file.
        """
        with open(self.config["device_topology_json_path"]) as f:
            device_topology = json.load(f)
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
        plugin_config = self.config.get("plugin", {})
        plugin_name = plugin_config.get("name", "qulacs")
        return plugin_name == "qulacs"

    def is_qpu(self) -> bool:
        """
        Check if the device is a QPU.
        """
        plugin_config = self.config.get("plugin", {})
        plugin_name = plugin_config.get("name", "qulacs")
        return plugin_name == "qubex"

    @property
    def device_topology(self) -> dict:
        """
        Returns the device topology, e.g., {"qubits": [{"id": 0, "physical_id": 5}], "couplings": [{"control": 0, "target": 1}]}
        """
        return self.load_device_topology()

    @property
    def device_status(self) -> dict:
        """
        Returns the device status, e.g., "active", "inactive", "maintenance"
        """
        return self.load_device_status()

    @property
    def device_info(self) -> dict:
        """
        Returns the device information, e.g., {"device_id": "QPU1", "device_type": "QPU"}
        """
        if self.is_simulator():
            self.config["device_info"]["type"] = "simulator"
        else:
            self.config["device_info"]["type"] = "QPU"
        return self.config["device_info"]

    @property
    def physical_map(self):
        """
        Returns the physical index to physical label mapping.
        The mapping is in the format physical_map: {'qubits': {0: 'Q29', 1: 'Q30', 2: 'Q31'}, 'couplings': {(2, 0): ('Q31', 'Q29'), (2, 1): ('Q31', 'Q30')}}"}
        """
        device_topology = self.load_device_topology()
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
    def _get_circuit(self) -> Any:
        """Get the circuit object for the backend.

        This method should be implemented in the derived class.
        """
        pass

    @abstractmethod
    def _execute(self, circuit: Any, shots: int = 1024) -> dict:
        """Execute the compiled circuit for a specified number of shots.

        This method should be implemented in the derived class.
        This method should return a dictionary with string keys and integer values,
        where the keys are binary strings representing measurement results
        and the values are the counts of those results.

        Args:
            circuit: The compiled circuit to be executed.
            shots: The number of shots to execute the circuit.
        Returns:
            A dictionary containing the counts of measurement results,
            e.g., {"000": 512, "111": 512}.

        """
        pass

    def _remove_zero_values(self, d: dict[str, int]) -> dict[str, int]:
        """Remove zero values from a dictionary.

        Args:
            d: Dictionary with string keys and integer values.
        Returns:
            Dictionary with zero values removed.

        """
        return {k: v for k, v in d.items() if v != 0}

    def execute(self, program: str, shots: int = 1024) -> tuple[dict, str]:
        """Execute the circuit for a specified number of shots.

        This method parses, compiles, and executes the circuit, and removes results with zero counts.

        Args:
            program: The circuit to be executed, given in OpenQASM 3 format.
            shots: The number of shots to execute the circuit.
        Returns:
            A tuple containing the counts of measurement results and a success message.
            The counts are in the format {"000": 512, "111": 512}.

        """
        qc = loads(program)
        circuit = self._get_circuit()
        compiled_circuit = circuit.compile(qc)
        counts = self._execute(compiled_circuit, shots=shots)
        counts = self._remove_zero_values(counts)
        logger.info(f"counts={counts}")

        return counts, SUCCESS_MESSAGE
