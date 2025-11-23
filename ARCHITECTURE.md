# Architecture Documentation

## Project Overview

This project implements a **real-time streaming Click-Through Rate (CTR) analytics pipeline** using Apache Flink and Apache Kafka. The system generates synthetic ad event streams, processes them in real-time using windowed aggregations, and calculates end-to-end latency metrics.

## System Purpose

The primary objective is to:
- Simulate realistic ad impression and click events with configurable workload patterns
- Process streaming data using Apache Flink's Table API with tumbling windows
- Calculate CTR (Click-Through Rate) per advertising campaign in real-time
- Measure and report end-to-end latency for performance analysis

## Architecture Components

### 1. **Data Generation Layer**

#### `data_generation.py`
- **Purpose**: Generates synthetic ad event data with realistic characteristics
- **Key Functions**:
  - `create_ad_campaign_mappings()`: Creates a fixed mapping of UUID-based ad IDs to campaign IDs
  - `generate_event_batch()`: Generates events with exponentially distributed inter-arrival times
- **Event Schema**:
  ```json
  {
    "user_id": "UUID",
    "page_id": "UUID",
    "ad_id": "UUID",
    "campaign_id": "integer",
    "ad_type": "string",
    "event_type": "view|click|purchase",
    "event_time_ns": "nanoseconds timestamp",
    "window_id": "integer",
    "ip_address": "string"
  }
  ```

#### `mmpp.py` (Markov-Modulated Poisson Process)
- **Purpose**: Models bursty traffic patterns using a two-state CTMC (Continuous-Time Markov Chain)
- **Functionality**: Generates correlated arrival rates that alternate between high and low states
- **Use Case**: Simulates realistic variable workload patterns (configurable via `DISTRIBUTION` setting)

### 2. **Message Broker Layer**

#### Apache Kafka Topics
- **`events`**: Primary input topic for raw ad events (3 partitions)
- **`results`**: Output topic for aggregated CTR results (1 partition)
- **`local-watermarks`**: Topic for watermark coordination (used in "none" mode)

#### Topic Configuration
- Configurable partition count and replication factor
- Timestamp type: `CreateTime` for events, `LogAppendTime` for results
- Automatic topic creation and cleanup via `producer.py` utilities

### 3. **Event Production Layer**

#### `producer.py`
- **Purpose**: Multi-process event generator that publishes to Kafka
- **Key Features**:
  - Supports multiple concurrent producer processes
  - Time-aligned event generation (synchronized to 10-second boundaries)
  - Supports both normal and MMPP distribution patterns
  - Sends END-OF-STREAM sentinel messages for coordination
- **Configuration**:
  - `NUM_PRODUCERS`: Number of parallel producer processes (default: 3)
  - `EVENTS_PER_PRODUCER`: Target throughput per producer (default: 5000 events)
  - `DURATION_SECONDS`: Duration of event generation (default: 60 seconds)

### 4. **Stream Processing Layer**

#### `flink_processor_table_api.py`
- **Purpose**: Real-time stream processing using Apache Flink Table API
- **Processing Logic**:
  1. Reads events from Kafka `events` topic
  2. Converts nanosecond timestamps to Flink TIMESTAMP type
  3. Applies watermarking strategy (3-second delay for late events)
  4. Groups by campaign_id and 10-second tumbling windows
  5. Calculates CTR: `clicks / (views + 1)`
  6. Writes aggregated results to `results` topic
- **Key Configuration**:
  - Tumbling window: 10 seconds
  - Watermark delay: 3 seconds
  - Parallelism: 1 (configurable)
  - Kafka connector JAR path (requires update for local environment)

#### Reference to DataStream API (Not Included)
- `flink_processor.py`: Alternative implementation using DataStream API
- `consumer.py`: Results consumer that writes to PostgreSQL
- `databaseOps.py`: Database operations layer

#### Reference to Spark Implementation (Not Included)
- `spark_processor.py`: Alternative implementation using Spark Structured Streaming

### 5. **Latency Measurement Layer**

#### `latency_calculator.py`
- **Purpose**: Measures end-to-end processing latency
- **Methodology**:
  1. Subscribes to `results` topic
  2. Compares producer event timestamp (`event_time_ns`) with Kafka result timestamp
  3. Tracks maximum latency per window
  4. Generates CSV report: `latency_report_{producers}_{events}_{distribution}.csv`
- **Output Format**:
  ```csv
  window_id,max_latency_ms
  0,123.45
  1,156.78
  ```

### 6. **Orchestration Layer**

#### `driver.py`
- **Purpose**: Main orchestration script that coordinates all pipeline components
- **Process Management**:
  - Spawns multiple producer processes
  - Starts Flink processor
  - Launches latency calculator
  - Optionally starts consumers (when `--skip-consumers` not set)
- **Execution Flow**:
  1. Setup Kafka topics (create/clear)
  2. Initialize ad-campaign mappings
  3. Optionally setup PostgreSQL database
  4. Align base timestamp to 10-second boundary
  5. Start all processes in coordinated sequence
  6. Wait for completion and generate reports
- **CLI Arguments**:
  - `--impl {spark|flink|none}`: Choose processing framework
  - `--skip-consumers`: Skip database consumers
  - `--num-producers`: Override number of producers
  - `--events-per-producer`: Override throughput
  - `--duration`: Override duration

### 7. **Configuration Management**

#### `config.py`
- **Purpose**: Centralized configuration for all components
- **Key Settings**:
  - Database connection parameters (PostgreSQL)
  - Kafka connection settings
  - Producer/consumer counts
  - Event generation parameters (campaigns, ads per campaign)
  - Topic names and partition configuration
  - Traffic distribution mode (`normal` or `mmpp`)

### 8. **Utility Scripts**

#### `clear_topics.py`
- **Purpose**: Standalone script to delete and recreate Kafka topics
- **Use Case**: Clean slate before running experiments

## Data Flow Architecture

```
┌─────────────────┐
│  Data Generator │
│ (data_generation)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Producer 1    │────▶│                 │     │                 │
├─────────────────┤     │  Kafka Broker   │     │  Flink Table    │
│   Producer 2    │────▶│   (events       │────▶│  API Processor  │
├─────────────────┤     │    topic)       │     │                 │
│   Producer N    │────▶│                 │     │  - Windowing    │
└─────────────────┘     └─────────────────┘     │  - Aggregation  │
         │                                       │  - CTR Calc     │
         │                                       └────────┬────────┘
         │                                                │
         │              ┌─────────────────┐               │
         │              │  Kafka Broker   │               │
         │              │   (results      │◀──────────────┘
         │              │    topic)       │
         │              └────────┬────────┘
         │                       │
         │                       │
         ▼                       ▼
┌─────────────────────────────────────┐
│      Latency Calculator             │
│  (measures end-to-end latency)      │
│                                     │
│  Tracks: event_time_ns →            │
│          result_kafka_timestamp     │
└─────────────────┬───────────────────┘
                  │
                  ▼
        ┌──────────────────┐
        │  latency_report  │
        │     (CSV)        │
        └──────────────────┘
```

## Technology Stack

### Core Technologies
- **Apache Flink 1.x**: Stream processing framework (Table API)
- **Apache Kafka**: Distributed message broker
- **Python 3.x**: Primary programming language
- **PyFlink**: Python API for Apache Flink

### Python Libraries
- `kafka-python`: Kafka client library
- `pyflink`: Flink Python bindings
- `numpy`: Numerical computations (MMPP, event generation)
- `uuid`: Unique identifier generation

### External Dependencies
- **Flink Kafka Connector JAR**: `flink-sql-connector-kafka-4.0.1-2.0.jar`
- **PostgreSQL**: Database for storing results (referenced but not in current codebase)

## Key Design Decisions

### 1. **Time Alignment Strategy**
- **Decision**: Align base event time to 10-second boundaries
- **Rationale**: Prevents window fracturing and ensures consistent window assignments
- **Implementation**: `base_event_time = int(time.time() // 10 * 10) - 10`

### 2. **Timestamp Handling**
- **Decision**: Use nanosecond precision (`event_time_ns`) throughout the pipeline
- **Rationale**: High-precision latency measurements and accurate event ordering
- **Conversion**: Flink converts ns to TIMESTAMP(3) for SQL operations

### 3. **Watermarking Strategy**
- **Decision**: 3-second watermark delay
- **Rationale**: Balance between latency and completeness (allow late events)
- **Trade-off**: Some very late events may be dropped

### 4. **Window Configuration**
- **Decision**: 10-second tumbling windows
- **Rationale**: Balance between real-time responsiveness and statistical significance
- **Window ID**: Relative to base time to ensure consistency across runs

### 5. **Traffic Pattern Modeling**
- **Decision**: Support both normal (Poisson) and MMPP distributions
- **Rationale**: MMPP provides realistic bursty traffic simulation
- **Configuration**: Toggle via `DISTRIBUTION` parameter in config.py

### 6. **Multi-Process Architecture**
- **Decision**: Use Python multiprocessing for producers and consumers
- **Rationale**: Achieve higher throughput by bypassing GIL limitations
- **Coordination**: Shared base timestamp and END sentinel messages

### 7. **Latency Measurement Approach**
- **Decision**: Track maximum latency per window (not average)
- **Rationale**: Max latency is critical for SLA compliance
- **Granularity**: Per-window measurement for detailed analysis

### 8. **Kafka Topic Design**
- **Decision**: Separate topics for events and results
- **Rationale**: Clean separation of concerns, different retention/partition requirements
- **Partitioning**: Multiple partitions for events (parallel producers), single partition for results (ordered aggregates)

## Configuration Parameters

### Workload Configuration
- `NUM_PRODUCERS = 3`: Number of parallel event generators
- `EVENTS_PER_PRODUCER = 5000`: Target events per producer
- `DURATION_SECONDS = 60`: Duration of event generation
- `NUM_CAMPAIGNS = 10`: Number of advertising campaigns
- `ADS_PER_CAMPAIGN = 100`: Ads per campaign (total: 1000 ads)

### Kafka Configuration
- `BOOTSTRAP_SERVERS = 'localhost:9092'`: Kafka broker address
- `PARTITIONS = 3`: Partitions for events topic
- `REPLICATION_FACTOR = 1`: Replication factor for topics

### Event Types
- `AD_TYPES = ['banner', 'video', 'popup', 'native', 'sponsored', 'interstitial', 'rewarded']`
- `EVENT_TYPES = ['view', 'click', 'purchase']`

## Deployment Considerations

### Prerequisites
1. **Apache Kafka**: Running on localhost:9092
2. **Apache Flink**: Proper Python environment with PyFlink
3. **Flink Kafka Connector**: JAR file must be available (update path in `flink_processor_table_api.py`)
4. **PostgreSQL** (optional): Only if running with consumers enabled

### Running the Pipeline

```bash
# Standard Flink execution
python driver.py --impl flink

# Skip database consumers
python driver.py --impl flink --skip-consumers

# Custom workload
python driver.py --impl flink --num-producers 5 --events-per-producer 10000 --duration 120

# Spark implementation (requires spark_processor.py)
python driver.py --impl spark

# No processor (testing producers/consumers only)
python driver.py --impl none
```

### Environment Setup Notes
- Update Flink JAR path in `flink_processor_table_api.py` (line 17) to match local installation
- Ensure Kafka topics are accessible and have sufficient storage
- Monitor Flink Web UI at `http://localhost:8085` during execution

## Performance Characteristics

### Expected Throughput
- **Default Configuration**: 3 producers × 5000 events = 15,000 events over 60 seconds ≈ 250 events/sec
- **Scalability**: Linear scaling with number of producers (limited by Kafka broker capacity)

### Latency Profile
- **Target**: Sub-second end-to-end latency for most windows
- **Factors Affecting Latency**:
  - Flink watermark delay (3 seconds)
  - Kafka message delivery time
  - Window triggering delay
  - Processing time in Flink

### Resource Requirements
- **Producers**: Minimal CPU, memory scales with batch size
- **Flink**: Memory-intensive (JVM), CPU depends on parallelism
- **Kafka**: Disk I/O for persistence, network bandwidth for replication

## Extension Points

### Adding New Event Types
1. Update `EVENT_TYPES` in `config.py`
2. Modify CTR calculation logic in `flink_processor_table_api.py` if needed

### Alternative Processing Frameworks
- Implement new processor following the `run_*_ctr_processor()` interface
- Register in `driver.py` with new `--impl` option

### Custom Traffic Patterns
- Extend `MMPPGenerator` class or create new distribution models
- Update `producer.py` to use new generator

### Additional Metrics
- Extend result schema in Flink SQL queries
- Update `latency_calculator.py` to track new metrics

## References

- [Apache Flink Documentation](https://flink.apache.org/)
- [Kafka Python Client](https://kafka-python.readthedocs.io/)
- [PyFlink Table API Guide](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/python/table/intro_to_table_api/)
