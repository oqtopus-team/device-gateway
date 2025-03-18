import argparse
import copy
import datetime
import json
import logging
from pathlib import Path
from typing import Optional

import networkx as nx
import yaml  # type: ignore[import]
from matplotlib import pyplot as plt

logger = logging.getLogger(__name__)


class DeviceInfoGenerator:
    def __init__(
        self,
        device_id: str,
        basis_gates_1q: list[str],
        basis_gates_2q: list[str],
        small_rows: int = 2,
        small_cols: int = 2,
        large_rows: int = 4,
        large_cols: int = 4,
        *,
        qubit_index_list: Optional[list[int]] = None,
        qubit_index_list_file: Optional[str] = None,
        system_note: dict = {},
        system_note_file: Optional[str] = None,
        is_simulator: bool = False,
    ):
        """
        Initialize parameters and either the data or file paths for qubit indices and system note.

        Args:
            device_id (str): Device ID.
            basis_gates_1q (list[str]): List of single-qubit basis gates.
            basis_gates_2q (list[str]): List of two-qubit basis gates.
            small_rows (int): Number of rows in the small lattice.
            small_cols (int): Number of columns in the small lattice.
            large_rows (int): Number of tile rows in the large lattice.
            large_cols (int): Number of tile columns in the large lattice.
            qubit_index_list (Optional[list[int]]): List of available physical qubit indices.
            qubit_index_list_file (Optional[str]): File path to the CSV file containing qubit indices.
            system_note (Optional[dict]): Dictionary containing calibration/system note information.
            system_note_file (Optional[str]): File path to the JSON file containing system note.
        """
        self.device_id = device_id
        self.basis_gates_1q = basis_gates_1q
        self.basis_gates_2q = basis_gates_2q
        self.small_rows = small_rows
        self.small_cols = small_cols
        self.large_rows = large_rows
        self.large_cols = large_cols

        # Either direct data or file path must be provided
        if qubit_index_list is None and qubit_index_list_file is None:
            raise ValueError(
                "Either qubit_index_list or qubit_index_list_file must be provided."
            )
        self.qubit_index_list = qubit_index_list
        self.qubit_index_list_file = qubit_index_list_file

        self.is_simulator = is_simulator
        if not self.is_simulator and system_note is None and system_note_file is None:
            raise ValueError(
                "Either system_note or system_note_file must be provided for non-simulator mode."
            )
        self.system_note = system_note
        self.system_note_file = system_note_file

        self.mapping: dict[tuple[int, int], int] = {}
        self.pos: dict[int, tuple[int, int]] = {}
        self.graph: nx.DiGraph = nx.DiGraph()
        self.available_qubit_indices: list[int] = []

    def load_qubit_index_list(self) -> None:
        """
        Set the available physical qubit indices.
        If a list is provided, use it directly; if a file path is provided, load from the CSV file.
        """
        if self.qubit_index_list is not None:
            self.available_qubit_indices = self.qubit_index_list
        elif self.qubit_index_list_file is not None:
            try:
                with open(self.qubit_index_list_file, "r") as f:
                    content = f.read().strip()
                self.available_qubit_indices = [int(x) for x in content.split(",")]
            except Exception as e:
                logger.error(f"Failed to load qubit index list from file: {e}")
                raise

    def _generate_dummy_system_note(self) -> dict:
        """
        Generate dummy system note data for simulation purposes.
        """
        if not self.available_qubit_indices:
            self.load_qubit_index_list()

        dummy_note: dict = {
            "average_gate_fidelity": {},
            "readout": {},
            "t1": {},
            "t2": {},
            "cr_params": {},
        }

        # Generate dummy data for each qubit
        for qubit in self.available_qubit_indices:
            qubit_key = f"Q{qubit:02}"
            # Set high fidelity values for simulation
            dummy_note["average_gate_fidelity"][qubit_key] = 0.999
            dummy_note["readout"][qubit_key] = {
                "prob_meas1_prep0": 0.001,
                "prob_meas0_prep1": 0.001,
                "readout_assignment_error": 0.001,
            }
            dummy_note["t1"][qubit_key] = 100.0  # microseconds
            dummy_note["t2"][qubit_key] = 100.0  # microseconds

        # Generate dummy data for couplings
        for i in range(len(self.available_qubit_indices)):
            for j in range(i + 1, len(self.available_qubit_indices)):
                q1 = self.available_qubit_indices[i]
                q2 = self.available_qubit_indices[j]
                coupling_key = f"Q{q1:02}-Q{q2:02}"
                dummy_note["cr_params"][coupling_key] = {"fidelity": 0.99}

        return dummy_note

    def load_system_note(self) -> None:
        """
        Set the calibration/system note information.
        For simulator mode, always use dummy data regardless of provided system note.
        For real device mode, use provided data or load from file.
        """
        if self.is_simulator:
            # Always use dummy data in simulator mode for ideal values
            self.system_note = self._generate_dummy_system_note()
            logger.info("Using dummy calibration data for simulator mode")
        else:
            if self.system_note is not None:
                return  # Data is already provided as a dictionary
            elif self.system_note_file is not None:
                try:
                    with open(self.system_note_file, "r") as f:
                        self.system_note = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load system note from file: {e}")
                    raise

    def generate_mapping_and_pos(self) -> None:
        """
        Tile the small lattice (small_rows x small_cols) into a large lattice (large_rows x large_cols),
        generating a mapping from grid coordinates to qubit indices and positions for visualization.
        """
        total_rows = self.small_rows * self.large_rows
        total_cols = self.small_cols * self.large_cols
        small_size = self.small_rows * self.small_cols

        for global_row in range(total_rows):
            for global_col in range(total_cols):
                # Determine the position within the small and large lattices
                large_row, small_row = divmod(global_row, self.small_rows)
                large_col, small_col = divmod(global_col, self.small_cols)

                # Compute indices within the large and small lattices
                large_index = large_row * self.large_cols + large_col
                small_index = small_row * self.small_cols + small_col
                qubit_index = large_index * small_size + small_index

                self.mapping[(global_row, global_col)] = qubit_index
                # Position for visualization (x: column, y: -row)
                self.pos[qubit_index] = (global_col, -global_row)

    def generate_full_topology(self) -> None:
        """
        Create an 8x8 grid graph, apply the mapping to generate the physical qubit graph,
        and then convert it into a directed graph.
        """
        grid = nx.grid_2d_graph(8, 8)
        if not self.mapping or not self.pos:
            self.generate_mapping_and_pos()

        mapped_grid = nx.relabel_nodes(grid, self.mapping)
        directed_graph = nx.DiGraph()
        for u, v in mapped_grid.edges():
            directed_graph.add_edge(u, v)
        self.graph = directed_graph

    def map_physical_to_virtual(self, physical_index: int) -> int:
        """
        Map a physical qubit index to a virtual qubit index.

        Raises:
            ValueError: If the physical index is not in the available list.
        """
        if not self.available_qubit_indices:
            self.load_qubit_index_list()
        if physical_index not in self.available_qubit_indices:
            raise ValueError(
                f"Physical qubit index {physical_index} is not available. "
                f"Available: {self.available_qubit_indices}"
            )
        virtual_index = self.available_qubit_indices.index(physical_index)
        logger.debug(
            f"Mapped physical qubit {physical_index} to virtual qubit {virtual_index}"
        )
        return virtual_index

    def map_virtual_to_physical(self, virtual_index: int) -> int:
        """
        Map a virtual qubit index to a physical qubit index.

        Raises:
            ValueError: If the virtual index is out of range.
        """
        if not self.available_qubit_indices:
            self.load_qubit_index_list()
        if virtual_index < 0 or virtual_index >= len(self.available_qubit_indices):
            raise ValueError(
                f"Virtual qubit index {virtual_index} is out of range (max {len(self.available_qubit_indices) - 1})."
            )
        physical_index = self.available_qubit_indices[virtual_index]
        logger.debug(
            f"Mapped virtual qubit {virtual_index} to physical qubit {physical_index}"
        )
        return physical_index

    def relabel_graph_physical_to_virtual(self) -> None:
        """
        Relabel the graph nodes from physical indices to virtual indices.
        Remove any nodes that are not available on the physical device.
        """
        mapping = {}
        new_pos = {}
        nodes_to_remove = []

        for physical_node in list(self.graph.nodes()):
            try:
                virtual_node = self.map_physical_to_virtual(physical_node)
                mapping[physical_node] = virtual_node
                new_pos[virtual_node] = self.pos[physical_node]
            except ValueError:
                logger.info(
                    f"Physical node {physical_node} not available in the real machine."
                )
                nodes_to_remove.append(physical_node)

        pruned_graph = copy.deepcopy(self.graph)
        pruned_graph.remove_nodes_from(nodes_to_remove)

        self.graph = nx.relabel_nodes(pruned_graph, mapping)
        self.pos = new_pos

    def set_qubit_and_edge_properties(self) -> None:
        """
        Set various properties for qubit nodes and coupling edges.
        If calibration information is not available, default values are used.
        """
        self.load_system_note()

        for virtual_node in list(self.graph.nodes()):
            physical_node = self.map_virtual_to_physical(virtual_node)
            physical_key = f"Q{physical_node:02}"

            # Always use the system note data, which will be either real calibration data
            # or dummy data for simulator mode
            node_data = {
                "id": virtual_node,
                "physical_id": physical_node,
                "position": {
                    "x": self.pos[virtual_node][0],
                    "y": self.pos[virtual_node][1],
                },
                "fidelity": self.system_note["average_gate_fidelity"].get(
                    physical_key, 0.0
                ),
                "meas_error": {
                    "prob_meas1_prep0": self.system_note["readout"]
                    .get(physical_key, {})
                    .get("prob_meas1_prep0", 0.0),
                    "prob_meas0_prep1": self.system_note["readout"]
                    .get(physical_key, {})
                    .get("prob_meas0_prep1", 0.0),
                    "readout_assignment_error": self.system_note["readout"]
                    .get(physical_key, {})
                    .get("readout_assignment_error", 0.0),
                },
                "qubit_lifetime": {
                    "t1": self.system_note["t1"].get(physical_key, 0.0),
                    "t2": self.system_note["t2"].get(physical_key, 0.0),
                },
                "gate_duration": {
                    gate: 20
                    for gate in ("rz", "sx", "x")
                    if gate in self.basis_gates_1q
                },
            }
            self.graph.nodes[virtual_node].update(node_data)

        for u, v in list(self.graph.edges()):
            physical_u = self.map_virtual_to_physical(u)
            physical_v = self.map_virtual_to_physical(v)
            coupling_key = f"Q{physical_u:02}-Q{physical_v:02}"

            # Use system note data for edge properties
            edge_data = {
                "control": u,
                "target": v,
                "fidelity": self.system_note.get("cr_params", {})
                .get(coupling_key, {})
                .get("fidelity", 0.99),
                "gate_duration": {
                    gate: 40 for gate in ("cx", "rzx90") if gate in self.basis_gates_2q
                },
            }
            self.graph.edges[u, v].update(edge_data)

    def dump_topology_json(self, output_json_file: str, indent: int = 2) -> None:
        """
        Output the device topology in JSON format.
        """
        topology = {
            "name": "test_device",
            "device_id": self.device_id,
            "qubits": sorted(
                [data for _, data in self.graph.nodes(data=True)], key=lambda d: d["id"]
            ),
            "couplings": sorted(
                [data for _, _, data in self.graph.edges(data=True)],
                key=lambda d: d["control"],
            ),
            "timestamp": str(datetime.datetime.now()),
        }
        json_output = json.dumps(topology, indent=indent)
        try:
            with open(output_json_file, "w") as f:
                f.write(json_output)
        except Exception as e:
            logger.error(f"Failed to dump topology JSON: {e}")
            raise

    def dump_topology_dict(self) -> dict:
        """
        Return the device topology as a dictionary.
        """
        topology = {
            "name": "test_device",
            "device_id": self.device_id,
            "qubits": sorted(
                [data for _, data in self.graph.nodes(data=True)], key=lambda d: d["id"]
            ),
            "couplings": sorted(
                [data for _, _, data in self.graph.edges(data=True)],
                key=lambda d: d["control"],
            ),
            "timestamp": str(datetime.datetime.now()),
        }
        return topology

    def dump_topology_png(
        self, output_png_file: str, figsize: tuple[int, int] = (5, 5)
    ) -> None:
        """
        Output the device topology as a PNG image.
        """
        plt.figure(figsize=figsize)
        nx.draw(
            self.graph,
            pos=self.pos,
            with_labels=True,
            node_color="white",
            edge_color="black",
            font_color="black",
            arrowsize=14,
        )
        plt.savefig(output_png_file)
        plt.close()

    def generate_device_topology(
        self,
        output_json_file: Optional[str] = None,
        output_png_file: Optional[str] = None,
        save: bool = False,
    ) -> None:
        """
        Execute all steps for generating the topology and, if requested,
        output the results as JSON and/or PNG.

        Steps:
          1. Load physical qubit indices.
          2. Generate the topology from an 8x8 grid.
          3. Relabel from physical to virtual indices.
          4. Apply calibration information to set properties.
          5. Output JSON/PNG if save is True.
        """
        self.load_qubit_index_list()
        self.generate_full_topology()
        self.relabel_graph_physical_to_virtual()
        self.load_system_note()
        self.set_qubit_and_edge_properties()
        if save:
            if output_json_file is not None:
                self.dump_topology_json(output_json_file)
            if output_png_file is not None:
                self.dump_topology_png(output_png_file)


def _parse_args() -> argparse.Namespace:
    """
    Parse command line arguments for the topology generator.
    """
    parser = argparse.ArgumentParser(
        description="Generate device topology information."
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to the server configuration file (YAML format).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Load configuration from YAML file
    with Path(args.config).open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    # Extract configuration values
    device_id = config["device_info"]["device_id"]
    is_simulator = config["simulator_mode"]
    qubit_index_list_path = config["qubit_index_list_path"]
    device_topology_json_path = config["device_topology_json_path"]

    # Generate PNG file path from JSON path
    device_topology_png_path = device_topology_json_path.replace(".json", ".png")

    generator = DeviceInfoGenerator(
        device_id=device_id,
        basis_gates_1q=["rz", "sx", "x"],
        basis_gates_2q=["cx", "rzx90"],
        qubit_index_list_file=qubit_index_list_path,
        is_simulator=is_simulator,
    )
    generator.generate_device_topology(
        output_json_file=device_topology_json_path,
        output_png_file=device_topology_png_path,
        save=True,
    )


if __name__ == "__main__":
    main()
