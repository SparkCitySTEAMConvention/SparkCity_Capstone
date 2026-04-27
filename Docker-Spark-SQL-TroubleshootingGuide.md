# Smart City IoT Pipeline - Troubleshooting Guide

## 🚨 Quick Emergency Fixes

### 🔥 "Everything is Broken" - Nuclear Option
```bash
# Stop everything and restart fresh
docker-compose down -v --remove-orphans
docker system prune -f
docker volume prune -f
docker-compose up -d --build
```

### ⚡ "Just Need to Restart" - Soft Reset
```bash
# Restart just the services
docker-compose restart
# Or restart specific service
docker-compose restart spark-master
```

---

## 🐳 Docker Issues

### 1. Container Won't Start

#### **Symptom**: `docker-compose up` fails or containers exit immediately

#### **Common Causes & Solutions**:

**Port Already in Use**
```bash
# Check what's using the port
lsof -i :8080  # For Spark UI
lsof -i :5432  # For PostgreSQL
lsof -i :8888  # For Jupyter

# Kill the process using the port
sudo kill -9 <PID>

# Or change ports in docker-compose.yml
ports:
  - "8081:8080"  # Use different host port
```

**Insufficient Memory**
```bash
# Check Docker resource allocation
docker system info | grep -i memory

# Increase Docker memory limit (Docker Desktop):
# Settings → Resources → Memory → Increase to 8GB+

# For Linux, check available memory
free -h
```

**Volume Mount Issues**
```bash
# Check if directories exist
ls -la data/
ls -la notebooks/

# Create missing directories
mkdir -p data/raw data/processed data/features
mkdir -p notebooks config sql

# Fix permissions
sudo chown -R $USER:$USER data/ notebooks/ config/
chmod -R 755 data/ notebooks/ config/
```

### 2. Cannot Connect to Services

#### **Symptom**: "Connection refused" when accessing Spark UI or Jupyter

#### **Solutions**:

**Check Container Status**
```bash
# See which containers are running
docker-compose ps

# Check logs for specific service
docker-compose logs spark-master
docker-compose logs jupyter
docker-compose logs postgres
```

**Network Issues**
```bash
# Check if services are listening
docker-compose exec spark-master netstat -tlnp | grep 8080
docker-compose exec postgres netstat -tlnp | grep 5432

# Test connectivity between containers
docker-compose exec jupyter ping spark-master
docker-compose exec jupyter ping postgres
```

**Firewall/Security Issues**
```bash
# Disable firewall temporarily (Linux)
sudo ufw disable

# For macOS, check System Preferences → Security & Privacy

# For Windows, check Windows Defender Firewall
```

### 3. Out of Disk Space

#### **Symptom**: "No space left on device"

#### **Solutions**:
```bash
# Check disk usage
df -h
docker system df

# Clean up Docker resources
docker system prune -a --volumes
docker builder prune -a

# Remove unused images
docker image prune -a

# Clean up old containers
docker container prune
```

### 4. Docker Compose Version Issues

#### **Symptom**: "version not supported" or syntax errors

#### **Solution**:
```bash
# Check Docker Compose version
docker-compose --version

# Update Docker Compose (Linux)
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# For older versions, use version 3.7 instead of 3.8 in docker-compose.yml
```

---

## ⚡ Spark Issues

### 1. Spark Session Creation Fails

#### **Symptom**: `Cannot connect to Spark master` or session creation hangs

#### **Common Causes & Solutions**:

**Master Not Running**
```python
# Check if Spark master is accessible
import requests
try:
    response = requests.get("http://localhost:8080")
    print("Spark master is running")
except:
    print("Cannot reach Spark master")
```

**Wrong Master URL**
```python
# Try different master configurations
# For local development
spark = SparkSession.builder.master("local[*]").getOrCreate()

# For Docker cluster
spark = SparkSession.builder.master("spark://spark-master:7077").getOrCreate()

# Check from inside Jupyter container
spark = SparkSession.builder.master("spark://localhost:7077").getOrCreate()
```

**Memory Configuration Issues**
```python
spark = (SparkSession.builder
         .appName("SmartCityIoTPipeline")
         .master("local[*]")
         .config("spark.driver.memory", "2g")  # Reduce if needed
         .config("spark.executor.memory", "1g")  # Reduce if needed
         .config("spark.driver.maxResultSize", "1g")
         .getOrCreate())
```

### 2. Out of Memory Errors

#### **Symptom**: `Java heap space` or `GC overhead limit exceeded`

#### **Solutions**:

**Increase Memory Allocation**
```python
spark.conf.set("spark.driver.memory", "4g")
spark.conf.set("spark.executor.memory", "2g")
spark.conf.set("spark.driver.maxResultSize", "2g")
```

**Optimize Data Processing**
```python
# Use sampling for large datasets
sample_df = large_df.sample(0.1, seed=42)

# Cache frequently used DataFrames
df.cache()
df.count()  # Trigger caching

# Repartition data
df = df.repartition(4)  # Fewer partitions for small datasets

# Use coalesce to reduce partitions
df = df.coalesce(2)
```

**Process Data in Chunks**
```python
# Process data month by month
for month in range(1, 13):
    monthly_data = df.filter(F.month("timestamp") == month)
    # Process monthly_data
    monthly_data.unpersist()  # Free memory
```

### 3. Slow Spark Jobs

#### **Symptom**: Jobs take very long time or appear to hang

#### **Solutions**:

**Check Spark UI for Bottlenecks**
- Open http://localhost:4040 (or 4041, 4042 if multiple sessions)
- Look at the Jobs tab for failed/slow stages
- Check Executors tab for resource usage

**Optimize Partitioning**
```python
# Check current partitions
print(f"Partitions: {df.rdd.getNumPartitions()}")

# Optimal partitions = 2-3x number of cores
optimal_partitions = spark.sparkContext.defaultParallelism * 2
df = df.repartition(optimal_partitions)
```

**Avoid Expensive Operations**
```python
# Avoid repeated .count() calls
count = df.count()
print(f"Records: {count}")

# Use .cache() for DataFrames used multiple times
df.cache()

# Avoid .collect() on large datasets
# Instead of:
all_data = df.collect()  # BAD: loads all data to driver

# Use:
sample_data = df.limit(1000).collect()  # GOOD: only sample
```

**Optimize Joins**
```python
# Broadcast small DataFrames
from pyspark.sql.functions import broadcast
result = large_df.join(broadcast(small_df), "key")

# Use appropriate join strategies
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
```

### 4. DataFrame Operations Fail

#### **Symptom**: `AnalysisException` or column not found errors

#### **Solutions**:

**Check Schema and Column Names**
```python
# Print schema to see exact column names
df.printSchema()

# Show column names
print(df.columns)

# Check for case sensitivity
df.select([F.col(c) for c in df.columns if 'timestamp' in c.lower()])
```

**Handle Null Values**
```python
# Check for nulls before operations
df.select([F.count(F.when(F.col(c).isNull(), c)).alias(c) for c in df.columns]).show()

# Drop nulls before joins
df_clean = df.na.drop(subset=['key_column'])

# Fill nulls with defaults
df_filled = df.na.fill({'numeric_col': 0, 'string_col': 'unknown'})
```

**Fix Data Type Issues**
```python
# Cast columns to correct types
df = df.withColumn("timestamp", F.to_timestamp("timestamp"))
df = df.withColumn("numeric_col", F.col("numeric_col").cast("double"))

# Handle string/numeric conversion errors
df = df.withColumn("safe_numeric", 
    F.when(F.col("string_col").rlike("^[0-9.]+$"), 
           F.col("string_col").cast("double")).otherwise(0))
```

---

## 🗄️ Database Connection Issues

### 1. Cannot Connect to PostgreSQL

#### **Symptom**: `Connection refused` or authentication failed

#### **Solutions**:

**Check PostgreSQL Status**
```bash
# Check if PostgreSQL container is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Test connection from host
psql -h localhost -p 5432 -U postgres -d smartcity
```

**From Jupyter/Spark Container**
```python
# Test database connection
import psycopg2

try:
    conn = psycopg2.connect(
        host="postgres",  # Use container name, not localhost
        port=5432,
        user="postgres",
        password="password",
        database="smartcity"
    )
    print("Database connection successful")
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")
```

**Spark JDBC Connection**
```python
# Correct JDBC URL for Docker
jdbc_url = "jdbc:postgresql://postgres:5432/smartcity"

# Test Spark database connection
test_df = spark.read.format("jdbc") \
    .option("url", jdbc_url) \
    .option("dbtable", "(SELECT 1 as test) as test_table") \
    .option("user", "postgres") \
    .option("password", "password") \
    .option("driver", "org.postgresql.Driver") \
    .load()

test_df.show()
```

### 2. JDBC Driver Issues

#### **Symptom**: `ClassNotFoundException: org.postgresql.Driver`

#### **Solutions**:

**Add JDBC Driver to Spark**
```python
spark = SparkSession.builder \
    .appName("SmartCityIoTPipeline") \
    .config("spark.jars.packages", "org.postgresql:postgresql:42.5.0") \
    .getOrCreate()
```

**Download Driver Manually**
```bash
# Download PostgreSQL JDBC driver
cd /opt/bitnami/spark/jars/
wget https://jdbc.postgresql.org/download/postgresql-42.5.0.jar
```

---

## 📊 Data Loading Issues

### 1. File Not Found Errors

#### **Symptom**: `FileNotFoundException` or path does not exist

#### **Solutions**:

**Check File Paths**
```python
import os

# Check if file exists
data_file = "data/raw/traffic_sensors.csv"
print(f"File exists: {os.path.exists(data_file)}")

# List directory contents
print(os.listdir("data/raw/"))

# Use absolute paths if needed
import os
abs_path = os.path.abspath("data/raw/traffic_sensors.csv")
df = spark.read.csv(abs_path, header=True, inferSchema=True)
```

**Volume Mount Issues**
```bash
# Check if volumes are mounted correctly
docker-compose exec jupyter ls -la /home/jovyan/work/data/

# Verify volume mounts in docker-compose.yml
volumes:
  - ./data:/home/jovyan/work/data
  - ./notebooks:/home/jovyan/work/notebooks
```

### 2. Schema Inference Problems

#### **Symptom**: Wrong data types or parsing errors

#### **Solutions**:

**Explicit Schema Definition**
```python
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType

# Define explicit schema
schema = StructType([
    StructField("sensor_id", StringType(), False),
    StructField("timestamp", StringType(), False),  # Read as string first
    StructField("vehicle_count", IntegerType(), True),
    StructField("avg_speed", DoubleType(), True)
])

df = spark.read.csv("data/raw/traffic_sensors.csv", 
                   header=True, schema=schema)

# Then convert timestamp
df = df.withColumn("timestamp", F.to_timestamp("timestamp"))
```

**Handle Different Date Formats**
```python
# Try different timestamp formats
df = df.withColumn("timestamp", 
    F.coalesce(
        F.to_timestamp("timestamp", "yyyy-MM-dd HH:mm:ss"),
        F.to_timestamp("timestamp", "MM/dd/yyyy HH:mm:ss"),
        F.to_timestamp("timestamp", "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'")
    ))
```

### 3. Large File Loading Issues

#### **Symptom**: Out of memory when loading large files

#### **Solutions**:

**Process Files in Chunks**
```python
# For very large CSV files, process line by line
def process_large_csv(file_path, chunk_size=10000):
    # Read in smaller chunks
    df = spark.read.option("maxRecordsPerFile", chunk_size) \
        .csv(file_path, header=True, inferSchema=True)
    return df

# Or split large files manually
# split -l 100000 large_file.csv chunk_
```

**Optimize File Format**
```python
# Convert to Parquet for better performance
df.write.mode("overwrite").parquet("data/processed/traffic_optimized.parquet")

# Read Parquet instead of CSV
df = spark.read.parquet("data/processed/traffic_optimized.parquet")
```

---

## 🔧 Environment Setup Issues

### 1. Python Package Conflicts

#### **Symptom**: `ImportError` or version conflicts

#### **Solutions**:

**Check Package Versions**
```python
import sys
print(f"Python version: {sys.version}")

import pyspark
print(f"PySpark version: {pyspark.__version__}")

import pandas
print(f"Pandas version: {pandas.__version__}")
```

**Rebuild Jupyter Container**
```bash
# Rebuild with latest packages
docker-compose down
docker-compose build --no-cache jupyter
docker-compose up -d
```

**Manual Package Installation**
```bash
# Install packages in running container
docker-compose exec jupyter pip install package_name

# Or add to requirements.txt and rebuild
```

### 2. Jupyter Notebook Issues

#### **Symptom**: Kernel won't start or crashes frequently

#### **Solutions**:

**Restart Jupyter Kernel**
- In Jupyter: Kernel → Restart & Clear Output

**Check Jupyter Logs**
```bash
docker-compose logs jupyter
```

**Increase Memory Limits**
```yaml
# In docker-compose.yml
jupyter:
  # ... other config
  deploy:
    resources:
      limits:
        memory: 4G
```

**Clear Jupyter Cache**
```bash
# Remove Jupyter cache
docker-compose exec jupyter rm -rf ~/.jupyter/
docker-compose restart jupyter
```

---

## 🚀 Performance Optimization Tips

### 1. Spark Configuration Tuning

```python
# Optimal Spark configuration for development
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")

# Memory optimization
spark.conf.set("spark.executor.memoryFraction", "0.8")
spark.conf.set("spark.sql.shuffle.partitions", "200")  # Adjust based on data size
```

### 2. Data Processing Best Practices

```python
# Cache DataFrames used multiple times
df.cache()
df.count()  # Trigger caching

# Use appropriate file formats
# CSV (slowest) → JSON → Parquet (fastest)

# Partition data for better performance
df.write.partitionBy("year", "month").parquet("partitioned_data")

# Use column pruning
df.select("col1", "col2").filter("col1 > 100")  # Better than df.filter().select()
```

### 3. Memory Management

```python
# Unpersist DataFrames when done
df.unpersist()

# Clear Spark context periodically
spark.catalog.clearCache()

# Monitor memory usage
print(f"Cached tables: {spark.catalog.listTables()}")
```

---

## 🐞 Debugging Strategies

### 1. Enable Debug Logging

```python
# Set log level for debugging
spark.sparkContext.setLogLevel("DEBUG")  # Very verbose
spark.sparkContext.setLogLevel("INFO")   # Moderate
spark.sparkContext.setLogLevel("WARN")   # Minimal (default)
```

### 2. Inspect Data at Each Step

```python
# Check DataFrame at each transformation
print(f"Step 1 - Rows: {df1.count()}, Columns: {len(df1.columns)}")
df1.show(5)

df2 = df1.filter(F.col("value") > 0)
print(f"Step 2 - Rows: {df2.count()}, Columns: {len(df2.columns)}")
df2.show(5)
```

### 3. Use Explain Plans

```python
# See execution plan
df.explain(True)

# Check for expensive operations
df.explain("cost")
```

### 4. Sample Data for Testing

```python
# Use small samples for development
sample_df = large_df.sample(0.01, seed=42)  # 1% sample

# Limit rows for testing
test_df = df.limit(1000)
```

---

## 📋 Health Check Commands

### Quick System Check Script

```bash
#!/bin/bash
echo "🔍 Smart City IoT Pipeline Health Check"
echo "======================================"

echo "📋 Docker Status:"
docker --version
docker-compose --version

echo "🐳 Container Status:"
docker-compose ps

echo "💾 Disk Usage:"
df -h
docker system df

echo "🧠 Memory Usage:"
free -h

echo "🌐 Network Connectivity:"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080 && echo " ✅ Spark UI accessible" || echo " ❌ Spark UI not accessible"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8888 && echo " ✅ Jupyter accessible" || echo " ❌ Jupyter not accessible"

echo "🗄️ Database Status:"
docker-compose exec -T postgres pg_isready -U postgres && echo " ✅ PostgreSQL ready" || echo " ❌ PostgreSQL not ready"

echo "📁 Data Files:"
ls -la data/raw/ 2>/dev/null && echo " ✅ Raw data found" || echo " ❌ Raw data missing"
```

### Python Health Check

```python
def health_check():
    """Run comprehensive health check"""
    checks = {
        "spark_session": False,
        "database_connection": False,
        "data_files": False,
        "memory_usage": False
    }
    
    # Check Spark session
    try:
        spark.sparkContext.statusTracker()
        checks["spark_session"] = True
        print("✅ Spark session healthy")
    except:
        print("❌ Spark session issues")
    
    # Check database
    try:
        test_df = spark.read.format("jdbc") \
            .option("url", "jdbc:postgresql://postgres:5432/smartcity") \
            .option("dbtable", "(SELECT 1) as test") \
            .option("user", "postgres") \
            .option("password", "password") \
            .load()
        test_df.count()
        checks["database_connection"] = True
        print("✅ Database connection healthy")
    except Exception as e:
        print(f"❌ Database issues: {e}")
    
    # Check data files
    try:
        import os
        required_files = [
            "data/raw/traffic_sensors.csv",
            "data/raw/air_quality.json", 
            "data/raw/weather_data.parquet"
        ]
        
        missing_files = [f for f in required_files if not os.path.exists(f)]
        if not missing_files:
            checks["data_files"] = True
            print("✅ All data files present")
        else:
            print(f"❌ Missing files: {missing_files}")
    except Exception as e:
        print(f"❌ File check failed: {e}")
    
    # Check memory usage
    try:
        import psutil
        memory_percent = psutil.virtual_memory().percent
        if memory_percent < 80:
            checks["memory_usage"] = True
            print(f"✅ Memory usage OK: {memory_percent:.1f}%")
        else:
            print(f"⚠️ High memory usage: {memory_percent:.1f}%")
    except:
        print("❓ Cannot check memory usage")
    
    overall_health = sum(checks.values()) / len(checks) * 100
    print(f"\n📊 Overall System Health: {overall_health:.1f}%")
    
    return checks

# Run health check
health_status = health_check()
```

---

## 🆘 When All Else Fails

### Complete Environment Reset

```bash
# Nuclear option - complete reset
docker-compose down -v --remove-orphans
docker system prune -a --volumes
docker builder prune -a

# Remove all project data (CAUTION!)
rm -rf data/processed/* data/features/*

# Rebuild everything
docker-compose build --no-cache
docker-compose up -d

# Regenerate sample data
python scripts/generate_data.py
```

### Get Help

1. **Check GitHub Issues**: Look for similar problems in the project repository
2. **Stack Overflow**: Search for Spark/Docker specific errors
3. **Spark Documentation**: https://spark.apache.org/docs/latest/
4. **Docker Documentation**: https://docs.docker.com/

### Collect Diagnostic Information

```bash
# Gather system information for help requests
echo "System Information:" > diagnostic_info.txt
uname -a >> diagnostic_info.txt
docker --version >> diagnostic_info.txt
docker-compose --version >> diagnostic_info.txt
python --version >> diagnostic_info.txt

echo "Container Status:" >> diagnostic_info.txt
docker-compose ps >> diagnostic_info.txt

echo "Container Logs:" >> diagnostic_info.txt
docker-compose logs --tail=50 >> diagnostic_info.txt

echo "Disk Usage:" >> diagnostic_info.txt
df -h >> diagnostic_info.txt
docker system df >> diagnostic_info.txt
```

---

## 📚 Additional Resources

- **Spark Tuning Guide**: https://spark.apache.org/docs/latest/tuning.html
- **Docker Best Practices**: https://docs.docker.com/develop/best-practices/
- **PySpark API Documentation**: https://spark.apache.org/docs/latest/api/python/
- **PostgreSQL Docker Guide**: https://hub.docker.com/_/postgres

Remember: Most issues are environment-related. When in doubt, restart containers and check logs! 🔄
