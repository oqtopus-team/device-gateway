#!/bin/bash
set -e

cp config/example/device_status config/device_status
echo "geneted config/device_status"
cp config/example/device_topology_request.json config/device_topology_request.json
echo "geneted config/device_topology_request.json"
cp config/example/device_topology.json config/device_topology.json
echo "geneted config/device_topology.json"
cp config/example/device_topology_sim.json config/device_topology_sim.json
echo "geneted config/device_topology_sim.json"
cp config/example/config.yaml config/config.yaml
echo "geneted config/config.yaml"
