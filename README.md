# Real-Time Data Pipeline with Kafka and Spark Streaming

This project demonstrates the implementation of a real-time data pipeline using Apache Kafka and Apache Spark Streaming. It is designed to capture, stream, and process data dynamically from various sources, making it ideal for scenarios that require real-time data analysis and decision-making.

## Project Overview

In this pipeline, data is ingested from external APIs, passed through Apache Kafka, and processed using Apache Spark Streaming. This setup allows for handling large volumes of data with low latency, providing timely insights into the streamed data.

### Components

- **API**: Acts as the data source, providing continuous data streams.
- **API**: Hosted on EC2 Instance on AWS.
- **Kafka Producer**: Responsible for ingesting data from the API and publishing it to a Kafka topic.
- **Apache Kafka**: Serves as a distributed message broker, buffering the data received from the producer before it is processed.
- **Spark Streaming**: Consumes messages from Kafka, processes them in real time, and can output the data to various sinks such as databases, dashboards, or storage systems.
- **Zookeeper**: Resource Manger.

