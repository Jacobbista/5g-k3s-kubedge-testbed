#!/bin/bash
set -e

echo "[MongoDB][init] Starting MongoDB initialization..."

# Create necessary directories
mkdir -p /var/lib/mongodb
mkdir -p /open5gs/install/var/log/open5gs

# Start MongoDB with the configuration
echo "[MongoDB][init] Starting MongoDB daemon..."
exec mongod --config /open5gs/install/etc/open5gs/mongodb.conf
