#!/bin/bash
cd kafka_2.13-3.8.0

BOOTSTRAP_SERVER="IP:9092"  #add public dns/ip
TOPIC_NAME="test_kafka_aws"

echo "Bootstrap Server : $BOOTSTRAP_SERVER"
#Start Zookeeper
echo "Starting Zookeeper"
bin/zookeeper-server-start.sh config/zookeeper.properties > "../logs/zookeeper.log" 2>&1 &
sleep 10

#Start Kafka
echo "Starting Kafka"
export KAFKA_HEAP_OPTS="-Xmx512M -Xms512M" 

bin/kafka-server-start.sh config/server.properties > "../logs/kafka.log" 2>&1 &
sleep 10

echo "Creating topic"
#bin/kafka-topics.sh --create --topic "$TOPIC_NAME" --bootstrap-server "$BOOTSTRAP_SERVER" --replication-factor 1 --partitions 1 > "../logs/topic_creation.log" 2>&1

#Start Producer
echo "Starting Producer"
bin/kafka-console-producer.sh --topic "$TOPIC_NAME" --bootstrap-server "$BOOTSTRAP_SERVER" 

#Start Consumer
#echo "Starting Consumer"
#bin/kafka-console-consumer.sh --topic "$TOPIC_NAME" --bootstrap-server "$BOOTSTRAP_SERVER" > "../logs/consumer.log" 2>&1 &
#sleep 10
