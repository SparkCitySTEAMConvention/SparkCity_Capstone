-- sql/init.sql
-- PostgreSQL Initialization Script for Smart City IoT Database

-- Create database schema
CREATE SCHEMA IF NOT EXISTS smartcity;
SET search_path TO smartcity;

-- Create sensor types lookup table
CREATE TABLE sensor_types (
    sensor_type_id SERIAL PRIMARY KEY,
    type_name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    measurement_unit VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sensor types
INSERT INTO sensor_types (type_name, description, measurement_unit) VALUES
('traffic', 'Traffic flow and speed sensors', 'vehicles/hour'),
('air_quality', 'Air pollution monitoring sensors', 'μg/m³'),
('weather', 'Weather monitoring stations', 'various'),
('energy', 'Energy consumption meters', 'kWh');

-- Create city zones table
CREATE TABLE zones (
    zone_id VARCHAR(20) PRIMARY KEY,
    zone_name VARCHAR(100) NOT NULL,
    zone_type VARCHAR(50) NOT NULL,
    lat_min DECIMAL(10,8) NOT NULL,
    lat_max DECIMAL(10,8) NOT NULL,
    lon_min DECIMAL(11,8) NOT NULL,
    lon_max DECIMAL(11,8) NOT NULL,
    population INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create sensors table
CREATE TABLE sensors (
    sensor_id VARCHAR(50) PRIMARY KEY,
    sensor_type_id INTEGER REFERENCES sensor_types(sensor_type_id),
    location_lat DECIMAL(10,8) NOT NULL,
    location_lon DECIMAL(11,8) NOT NULL,
    zone_id VARCHAR(20) REFERENCES zones(zone_id),
    installation_date DATE,
    last_maintenance DATE,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create main sensor readings table (fact table)
CREATE TABLE sensor_readings (
    reading_id BIGSERIAL PRIMARY KEY,
    sensor_id VARCHAR(50) REFERENCES sensors(sensor_id),
    timestamp TIMESTAMP NOT NULL,
    measurement_type VARCHAR(50) NOT NULL,
    value DECIMAL(15,6),
    unit VARCHAR(20),
    quality_score DECIMAL(3,2) DEFAULT 1.0,
    anomaly_flag BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create specific tables for each sensor type

-- Traffic sensor readings
CREATE TABLE traffic_readings (
    reading_id BIGSERIAL PRIMARY KEY,
    sensor_id VARCHAR(50) REFERENCES sensors(sensor_id),
    timestamp TIMESTAMP NOT NULL,
    vehicle_count INTEGER,
    avg_speed DECIMAL(5,2),
    congestion_level VARCHAR(20),
    road_type VARCHAR(50),
    quality_score DECIMAL(3,2) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Air quality readings
CREATE TABLE air_quality_readings (
    reading_id BIGSERIAL PRIMARY KEY,
    sensor_id VARCHAR(50) REFERENCES sensors(sensor_id),
    timestamp TIMESTAMP NOT NULL,
    pm25 DECIMAL(8,3),
    pm10 DECIMAL(8,3),
    no2 DECIMAL(8,3),
    co DECIMAL(8,4),
    temperature DECIMAL(5,2),
    humidity DECIMAL(5,2),
    quality_score DECIMAL(3,2) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Weather readings
CREATE TABLE weather_readings (
    reading_id BIGSERIAL PRIMARY KEY,
    station_id VARCHAR(50) REFERENCES sensors(sensor_id),
    timestamp TIMESTAMP NOT NULL,
    temperature DECIMAL(5,2),
    humidity DECIMAL(5,2),
    wind_speed DECIMAL(5,2),
    wind_direction DECIMAL(5,2),
    precipitation DECIMAL(6,3),
    pressure DECIMAL(7,2),
    quality_score DECIMAL(3,2) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Energy consumption readings
CREATE TABLE energy_readings (
    reading_id BIGSERIAL PRIMARY KEY,
    meter_id VARCHAR(50) REFERENCES sensors(sensor_id),
    timestamp TIMESTAMP NOT NULL,
    building_type VARCHAR(50),
    power_consumption DECIMAL(10,3),
    voltage DECIMAL(6,2),
    current DECIMAL(8,3),
    power_factor DECIMAL(4,3),
    quality_score DECIMAL(3,2) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create aggregated tables for common queries

-- Hourly aggregations
CREATE TABLE hourly_aggregates (
    aggregate_id BIGSERIAL PRIMARY KEY,
    zone_id VARCHAR(20) REFERENCES zones(zone_id),
    sensor_type VARCHAR(50),
    hour_timestamp TIMESTAMP NOT NULL,
    metric_name VARCHAR(100),
    avg_value DECIMAL(15,6),
    min_value DECIMAL(15,6),
    max_value DECIMAL(15,6),
    count_readings INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily aggregations
CREATE TABLE daily_aggregates (
    aggregate_id BIGSERIAL PRIMARY KEY,
    zone_id VARCHAR(20) REFERENCES zones(zone_id),
    sensor_type VARCHAR(50),
    date_day DATE NOT NULL,
    metric_name VARCHAR(100),
    avg_value DECIMAL(15,6),
    min_value DECIMAL(15,6),
    max_value DECIMAL(15,6),
    count_readings INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_sensor_readings_timestamp ON sensor_readings(timestamp);
CREATE INDEX idx_sensor_readings_sensor_id ON sensor_readings(sensor_id);
CREATE INDEX idx_traffic_readings_timestamp ON traffic_readings(timestamp);
CREATE INDEX idx_air_quality_readings_timestamp ON air_quality_readings(timestamp);
CREATE INDEX idx_weather_readings_timestamp ON weather_readings(timestamp);
CREATE INDEX idx_energy_readings_timestamp ON energy_readings(timestamp);

-- Create composite indexes for common query patterns
CREATE INDEX idx_sensor_readings_sensor_timestamp ON sensor_readings(sensor_id, timestamp);
CREATE INDEX idx_traffic_readings_sensor_timestamp ON traffic_readings(sensor_id, timestamp);
CREATE INDEX idx_hourly_aggregates_zone_type_time ON hourly_aggregates(zone_id, sensor_type, hour_timestamp);

-- Create views for common analytical queries

-- Current sensor status view
CREATE VIEW current_sensor_status AS
SELECT 
    s.sensor_id,
    st.type_name as sensor_type,
    s.location_lat,
    s.location_lon,
    s.zone_id,
    z.zone_name,
    z.zone_type,
    s.status,
    CASE 
        WHEN sr.last_reading < NOW() - INTERVAL '1 hour' THEN 'stale'
        WHEN sr.last_reading < NOW() - INTERVAL '6 hours' THEN 'warning'
        ELSE 'active'
    END as data_status,
    sr.last_reading
FROM sensors s
JOIN sensor_types st ON s.sensor_type_id = st.sensor_type_id
LEFT JOIN zones z ON s.zone_id = z.zone_id
LEFT JOIN (
    SELECT 
        sensor_id,
        MAX(timestamp) as last_reading
    FROM sensor_readings
    GROUP BY sensor_id
) sr ON s.sensor_id = sr.sensor_id;

-- Zone summary view
CREATE VIEW zone_summary AS
SELECT 
    z.zone_id,
    z.zone_name,
    z.zone_type,
    z.population,
    COUNT(DISTINCT s.sensor_id) as total_sensors,
    COUNT(DISTINCT CASE WHEN s.status = 'active' THEN s.sensor_id END) as active_sensors,
    COUNT(DISTINCT st.type_name) as sensor_types_count
FROM zones z
LEFT JOIN sensors s ON z.zone_id = s.zone_id
LEFT JOIN sensor_types st ON s.sensor_type_id = st.sensor_type_id
GROUP BY z.zone_id, z.zone_name, z.zone_type, z.population;

-- Grant permissions for application user
CREATE USER spark_user WITH PASSWORD 'spark_password';
GRANT USAGE ON SCHEMA smartcity TO spark_user;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA smartcity TO spark_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA smartcity TO spark_user;

-- Add comments for documentation
COMMENT ON TABLE sensor_readings IS 'Main fact table for all sensor measurements';
COMMENT ON TABLE zones IS 'City zones and districts definition';
COMMENT ON TABLE sensors IS 'Sensor registry with locations and metadata';
COMMENT ON VIEW current_sensor_status IS 'Real-time view of sensor operational status';

-- Create function for data quality scoring
CREATE OR REPLACE FUNCTION calculate_data_quality_score(
    missing_values INTEGER,
    total_values INTEGER,
    outlier_count INTEGER
) RETURNS DECIMAL(3,2) AS $$
BEGIN
    -- Simple data quality scoring algorithm
    -- 1.0 = perfect quality, 0.0 = poor quality
    IF total_values = 0 THEN
        RETURN 0.0;
    END IF;
    
    RETURN GREATEST(0.0, 
        1.0 - (missing_values::DECIMAL / total_values) * 0.5 
            - (outlier_count::DECIMAL / total_values) * 0.3
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_data_quality_score IS 'Calculate data quality score based on missing values and outliers';

