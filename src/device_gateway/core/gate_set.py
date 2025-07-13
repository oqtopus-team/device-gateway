"""Gate set definition for quantum circuits."""

# Supported gates in the device
SUPPORTED_GATES = {
    "x",  # X gate (NOT)
    "sx",  # sqrt(X) gate
    "rz",  # RZ gate (rotation around Z)
    "cx",  # CNOT gate
    "measure",
    "barrier",
    "delay",
}
