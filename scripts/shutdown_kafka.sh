#!/bin/bash

echo "Forcefully terminating any remaining Kafka-related processes..."
ps aux | grep '[k]afka' | awk '{print $2}' | xargs -r kill -9