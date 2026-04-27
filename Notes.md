# Smart City IoT Analytics Pipeline
## 5-Day PySpark Data Engineering Lab

### 🎯 Project Overview

Build a comprehensive data pipeline that ingests, processes, and analyzes IoT sensor data from a smart city infrastructure. Students will use PySpark to handle large-scale sensor data, perform real-time analytics, and create actionable insights for city operations through an interactive dashboard.

### 🎓 Learning Objectives

By the end of this project, students will be able to:

- Set up and configure a distributed Spark cluster using Docker
- Ingest and process multi-format IoT data streams using PySpark
- Implement data quality checks and cleaning procedures for sensor data
- Perform time-series analysis and anomaly detection on large datasets
- Design and optimize data pipelines for real-time processing
- Integrate Spark with RDBMS (PostgreSQL) for data persistence
- Create monitoring dashboards for operational insights
- Apply best practices for data engineering workflows

### 📊 Data Sources & Schema

#### Primary Datasets (Simulated Smart City Data)

**1. Traffic Sensors (`traffic_sensors.csv`)**
```sql
sensor_id: string
timestamp: timestamp
location_lat: double
location_lon: double
vehicle_count: integer
avg_speed: double
congestion_level: string
road_type: string
```

**2. Air Quality Monitors (`air_quality.json`)**
```sql
sensor_id: string
timestamp: timestamp
location_lat: double
location_lon: double
pm25: double
pm10: double
no2: double
co: double
temperature: double
humidity: double
```

**3. Weather Stations (`weather_data.parquet`)**
```sql
station_id: string
timestamp: timestamp
location_lat: double
location_lon: double
temperature: double
humidity: double
wind_speed: double
wind_direction: double
precipitation: double
pressure: double
```

**4. Energy Consumption (`energy_meters.csv`)**
```sql
meter_id: string
timestamp: timestamp
building_type: string
location_lat: double
location_lon: double
power_consumption: double
voltage: double
current: double
power_factor: double
```

**5. Reference Data (`city_zones.csv`)**
```sql
zone_id: string
zone_name: string
zone_type: string
lat_min: double
lat_max: double
lon_min: double
lon_max: double
population: integer
```

### 🛠 Technical Requirements

#### Infrastructure
- **Spark Cluster:** 3-node cluster (1 master, 2 workers) via Docker Compose
- **Database:** PostgreSQL 13+ for data persistence
- **Dashboard:** Grafana or Streamlit for visualization
- **Storage:** Local filesystem with HDFS simulation
- **Languages:** Python 3.8+, SQL

#### Python Dependencies
```
pyspark==3.4.0
pandas==1.5.3
psycopg2-binary==2.9.5
matplotlib==3.6.3
seaborn==0.12.2
streamlit==1.20.0
plotly==5.13.1
requests==2.28.2
```

### 📅 Daily Breakdown

## Day 1: Environment Setup & Data Exploration
**Duration:** 8 hours  
**Focus:** Infrastructure setup, data ingestion, basic transformations

### Learning Objectives
- Configure Spark cluster and development environment
- Understand IoT data characteristics and challenges
- Implement basic data ingestion patterns
- Explore PySpark DataFrame operations

### Tasks

#### Morning (4 hours)
1. **Environment Setup (2 hours)**
   - Clone repository and review project structure
   - Start Docker Compose cluster (Spark + PostgreSQL)
   - Verify Spark UI and database connectivity
   - Configure Jupyter notebook with PySpark

2. **Data Exploration (2 hours)**
   - Load sample datasets into Spark DataFrames
   - Examine data schemas and quality issues
   - Generate basic statistics for each data source
   - Identify missing values and outliers

#### Afternoon (4 hours)
3. **Basic Data Ingestion (2 hours)**
   - Implement CSV, JSON, and Parquet readers
   - Handle schema inference and enforcement
   - Create reusable data loading functions
   - Set up data validation checks

4. **Initial Data Transformations (2 hours)**
   - Standardize timestamp formats across datasets
   - Add derived columns (hour, day, week)
   - Implement basic data type conversions
   - Create geographical zone mappings

### Deliverables
- Working Spark cluster with all services running
- Data ingestion notebook with basic EDA
- Documentation of data quality findings
- Initial data loading pipeline functions

### Key Concepts Covered
- Spark cluster architecture and configuration
- DataFrame creation and basic operations
- Schema management and data types
- File format handling (CSV, JSON, Parquet)

---

## Day 2: Data Quality & Cleaning Pipeline
**Duration:** 8 hours  
**Focus:** Data quality assessment, cleaning procedures, standardization

### Learning Objectives
- Implement comprehensive data quality checks
- Design cleaning procedures for IoT sensor data
- Handle missing values and outliers appropriately
- Create reusable data quality functions

### Tasks

#### Morning (4 hours)
1. **Data Quality Assessment (2 hours)**
   - Develop data profiling functions
   - Identify anomalies in sensor readings
   - Check for duplicate records across time series
   - Analyze temporal patterns and gaps

2. **Missing Data Strategy (2 hours)**
   - Implement interpolation for time series gaps
   - Create business rules for acceptable missing data
   - Design backfill procedures for critical sensors
   - Handle sensors with extended outages

#### Afternoon (4 hours)
3. **Outlier Detection & Treatment (2 hours)**
   - Implement statistical outlier detection (IQR, Z-score)
   - Create domain-specific validation rules
   - Design outlier treatment strategies
   - Build alerting for anomalous readings

4. **Data Standardization (2 hours)**
   - Standardize location coordinates
   - Normalize sensor measurement units
   - Create consistent naming conventions
   - Implement data lineage tracking

### Deliverables
- Data quality assessment report
- Comprehensive cleaning pipeline
- Outlier detection and treatment functions
- Standardized datasets ready for analysis

### Key Concepts Covered
- Data profiling techniques in Spark
- Time series data quality challenges
- Statistical outlier detection methods
- Data validation and business rules

---

## Day 3: Time Series Analysis & Feature Engineering
**Duration:** 8 hours  
**Focus:** Temporal analysis, correlation studies, feature creation

### Learning Objectives
- Perform time series analysis on sensor data
- Calculate correlations between different sensor types
- Engineer features for predictive modeling
- Implement window functions for trend analysis

### Tasks

#### Morning (4 hours)
1. **Temporal Pattern Analysis (2 hours)**
   - Analyze hourly, daily, and weekly patterns
   - Identify seasonal trends in sensor data
   - Calculate moving averages and trend indicators
   - Detect pattern anomalies and shifts

2. **Cross-Sensor Correlation Analysis (2 hours)**
   - Correlate air quality with traffic patterns
   - Analyze weather impact on energy consumption
   - Study relationships between sensor proximity
   - Create correlation matrices and heatmaps

#### Afternoon (4 hours)
3. **Feature Engineering (3 hours)**
   - Create lag features for time series prediction
   - Calculate rolling statistics (mean, std, min, max)
   - Engineer interaction features between sensors
   - Build aggregated features by city zones

4. **Trend Analysis (1 hour)**
   - Implement trend detection algorithms
   - Calculate rate of change indicators
   - Identify long-term vs short-term patterns
   - Create trend visualization functions

### Deliverables
- Time series analysis dashboard
- Correlation study findings
- Feature engineering pipeline
- Trend analysis reports

### Key Concepts Covered
- Window functions in Spark SQL
- Time series feature engineering
- Statistical correlation analysis
- Temporal pattern recognition

---

## Day 4: Advanced Analytics & Anomaly Detection
**Duration:** 8 hours  
**Focus:** Predictive modeling, anomaly detection, optimization

### Learning Objectives
- Implement machine learning pipelines in PySpark
- Build anomaly detection systems for IoT data
- Optimize pipeline performance and resource usage
- Create predictive models for city operations

### Tasks

#### Morning (4 hours)
1. **Anomaly Detection System (2 hours)**
   - Implement isolation forest for multivariate anomalies
   - Create threshold-based alerting systems
   - Build real-time anomaly scoring
   - Design anomaly investigation workflows

2. **Predictive Modeling (2 hours)**
   - Build traffic congestion prediction models
   - Create air quality forecasting pipeline
   - Implement energy demand prediction
   - Validate model performance and accuracy

#### Afternoon (4 hours)
3. **Pipeline Optimization (2 hours)**
   - Implement data partitioning strategies
   - Optimize Spark configurations for performance
   - Add caching for frequently accessed data
   - Monitor resource utilization and bottlenecks

4. **Advanced Analytics (2 hours)**
   - Implement clustering for sensor grouping
   - Create recommendation systems for city planning
   - Build alerting systems for critical thresholds
   - Design automated response triggers

### Deliverables
- Anomaly detection system with alerting
- Predictive models with validation metrics
- Optimized pipeline with performance benchmarks
- Advanced analytics dashboard

### Key Concepts Covered
- MLlib for machine learning in Spark
- Performance tuning and optimization
- Real-time stream processing concepts
- Advanced statistical modeling techniques

---

## Day 5: Database Integration & Dashboard Creation
**Duration:** 8 hours  
**Focus:** Data persistence, dashboard development, deployment

### Learning Objectives
- Integrate Spark with PostgreSQL for data persistence
- Design efficient database schemas for analytics
- Create interactive dashboards for city operations
- Implement automated pipeline scheduling

### Tasks

#### Morning (4 hours)
1. **Database Schema Design (1 hour)**
   - Design star schema for analytics
   - Create optimized table structures
   - Implement proper indexing strategies
   - Set up data retention policies

2. **Data Pipeline to Database (3 hours)**
   - Implement Spark-to-PostgreSQL connectors
   - Create batch and streaming write operations
   - Design upsert operations for real-time updates
   - Implement data quality checks before writes

#### Afternoon (4 hours)
3. **Dashboard Development (3 hours)**
   - Create real-time city operations dashboard
   - Build interactive visualizations for each sensor type
   - Implement drill-down capabilities
   - Add alerting and notification features

4. **Pipeline Automation (1 hour)**
   - Create scheduling workflows
   - Implement error handling and recovery
   - Set up monitoring and logging
   - Document deployment procedures

### Deliverables
- Production-ready database schema
- Automated data pipeline with scheduling
- Interactive city operations dashboard
- Complete project documentation

### Key Concepts Covered
- Spark-RDBMS integration patterns
- Dashboard design principles
- Pipeline automation and monitoring
- Production deployment considerations

---

### 🏗 Project Structure

```
smart-city-iot-pipeline/
├── README.md
├── requirements.txt
├── docker-compose.yml
├── config/
│   ├── spark-defaults.conf
│   └── postgres-init.sql
├── data/
│   ├── raw/
│   ├── processed/
│   └── reference/
├── notebooks/
│   ├── day1_setup_and_exploration.ipynb
│   ├── day2_data_quality_cleaning.ipynb
│   ├── day3_time_series_analysis.ipynb
│   ├── day4_advanced_analytics.ipynb
│   └── day5_dashboard_deployment.ipynb
├── src/
│   ├── data_ingestion/
│   ├── data_quality/
│   ├── analytics/
│   ├── models/
│   └── utils/
├── sql/
│   ├── create_tables.sql
│   └── analytical_queries.sql
├── dashboard/
│   ├── app.py
│   └── templates/
├── tests/
│   └── test_pipeline.py
└── docs/
    ├── setup_guide.md
    ├── daily_objectives.md
    └── troubleshooting.md
```

### 📝 Assessment Criteria

#### Technical Implementation (60%)
- **Code Quality:** Clean, documented, following PySpark best practices
- **Data Pipeline:** Robust ingestion, cleaning, and transformation
- **Performance:** Efficient use of Spark features and optimizations
- **Database Integration:** Proper schema design and data persistence

#### Analytics & Insights (25%)
- **Data Quality:** Comprehensive cleaning and validation
- **Analysis Depth:** Meaningful insights from sensor data
- **Visualization:** Clear, informative dashboard design
- **Anomaly Detection:** Effective identification of unusual patterns

#### Documentation & Presentation (15%)
- **Code Documentation:** Clear comments and README files
- **Daily Deliverables:** Complete notebook submissions
- **Final Presentation:** Clear explanation of insights and architecture
- **Reproducibility:** Others can run the pipeline successfully

### 🚀 Getting Started

1. **Prerequisites Check:**
   - Docker and Docker Compose installed
   - Python 3.8+ with pip
   - Git for version control
   - 8GB+ RAM recommended

2. **Repository Setup:**
   ```bash
   git clone [repository-url]
   cd smart-city-iot-pipeline
   pip install -r requirements.txt
   ```

3. **Start Infrastructure:**
   ```bash
   docker-compose up -d
   # Wait for services to be ready (check logs)
   docker-compose logs -f
   ```

4. **Verify Setup:**
   - Spark UI: http://localhost:8080
   - Jupyter: http://localhost:8888
   - Database: localhost:5432

5. **Begin Day 1 Activities:**
   - Open `notebooks/day1_setup_and_exploration.ipynb`
   - Follow daily objectives and complete tasks
   - Submit deliverables at end of each day

### 🆘 Support Resources

- **Spark Documentation:** https://spark.apache.org/docs/latest/
- **PySpark API Reference:** https://spark.apache.org/docs/latest/api/python/
- **PostgreSQL Documentation:** https://www.postgresql.org/docs/
- **Project Issues:** Use GitHub Issues for technical questions
- **Daily Check-ins:** Instructor availability for guidance

### 🎉 Success Metrics

By project completion, students will have:
- ✅ Built a production-ready data pipeline processing 1M+ sensor readings
- ✅ Implemented comprehensive data quality and anomaly detection
- ✅ Created actionable insights for smart city operations
- ✅ Developed skills in distributed data processing with Spark
- ✅ Gained experience with modern data engineering tools and practices

---

*Ready to build the future of smart cities? Let's get started!* 🏙️⚡
