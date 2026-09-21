BEGIN;

CREATE SCHEMA IF NOT EXISTS sparkcity;

CREATE TABLE IF NOT EXISTS sparkcity.traffic_sensors (
    sensor_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    location_lat DOUBLE PRECISION NOT NULL CHECK (location_lat BETWEEN -90 AND 90),
    location_lon DOUBLE PRECISION NOT NULL CHECK (location_lon BETWEEN -180 AND 180),
    vehicle_count INTEGER NOT NULL CHECK (vehicle_count >= 0),
    avg_speed DOUBLE PRECISION NOT NULL CHECK (avg_speed >= 0),
    congestion_level TEXT NOT NULL CHECK (congestion_level IN ('low', 'medium', 'high')),
    road_type TEXT NOT NULL,
    PRIMARY KEY (sensor_id, timestamp)
);

CREATE TABLE IF NOT EXISTS sparkcity.air_quality (
    sensor_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    location_lat DOUBLE PRECISION NOT NULL CHECK (location_lat BETWEEN -90 AND 90),
    location_lon DOUBLE PRECISION NOT NULL CHECK (location_lon BETWEEN -180 AND 180),
    pm25 DOUBLE PRECISION NOT NULL CHECK (pm25 >= 0),
    pm10 DOUBLE PRECISION NOT NULL CHECK (pm10 >= 0),
    no2 DOUBLE PRECISION NOT NULL CHECK (no2 >= 0),
    co DOUBLE PRECISION NOT NULL CHECK (co >= 0),
    temperature DOUBLE PRECISION NOT NULL,
    humidity DOUBLE PRECISION NOT NULL CHECK (humidity BETWEEN 0 AND 100),
    PRIMARY KEY (sensor_id, timestamp)
);

CREATE TABLE IF NOT EXISTS sparkcity.weather_data (
    station_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    location_lat DOUBLE PRECISION NOT NULL CHECK (location_lat BETWEEN -90 AND 90),
    location_lon DOUBLE PRECISION NOT NULL CHECK (location_lon BETWEEN -180 AND 180),
    temperature DOUBLE PRECISION NOT NULL,
    humidity DOUBLE PRECISION NOT NULL CHECK (humidity BETWEEN 0 AND 100),
    wind_speed DOUBLE PRECISION NOT NULL CHECK (wind_speed >= 0),
    wind_direction DOUBLE PRECISION NOT NULL CHECK (wind_direction BETWEEN 0 AND 360),
    precipitation DOUBLE PRECISION NOT NULL CHECK (precipitation >= 0),
    pressure DOUBLE PRECISION NOT NULL CHECK (pressure >= 0),
    PRIMARY KEY (station_id, timestamp)
);

CREATE TABLE IF NOT EXISTS sparkcity.energy_meters (
    meter_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    building_type TEXT NOT NULL,
    location_lat DOUBLE PRECISION NOT NULL CHECK (location_lat BETWEEN -90 AND 90),
    location_lon DOUBLE PRECISION NOT NULL CHECK (location_lon BETWEEN -180 AND 180),
    power_consumption DOUBLE PRECISION NOT NULL CHECK (power_consumption >= 0),
    voltage DOUBLE PRECISION NOT NULL CHECK (voltage >= 0),
    current DOUBLE PRECISION NOT NULL CHECK (current >= 0),
    power_factor DOUBLE PRECISION NOT NULL CHECK (power_factor BETWEEN 0 AND 1),
    PRIMARY KEY (meter_id, timestamp)
);

CREATE TABLE IF NOT EXISTS sparkcity.city_zones (
    zone_id TEXT PRIMARY KEY,
    zone_name TEXT NOT NULL,
    zone_type TEXT NOT NULL,
    lat_min DOUBLE PRECISION NOT NULL CHECK (lat_min BETWEEN -90 AND 90),
    lat_max DOUBLE PRECISION NOT NULL CHECK (lat_max BETWEEN -90 AND 90),
    lon_min DOUBLE PRECISION NOT NULL CHECK (lon_min BETWEEN -180 AND 180),
    lon_max DOUBLE PRECISION NOT NULL CHECK (lon_max BETWEEN -180 AND 180),
    population INTEGER NOT NULL CHECK (population >= 0),
    CHECK (lat_min <= lat_max),
    CHECK (lon_min <= lon_max)
);

CREATE TABLE IF NOT EXISTS sparkcity.occupancy_data (
    sensor_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    location_lat DOUBLE PRECISION NOT NULL CHECK (location_lat BETWEEN -90 AND 90),
    location_lon DOUBLE PRECISION NOT NULL CHECK (location_lon BETWEEN -180 AND 180),
    available_rooms INTEGER NOT NULL CHECK (available_rooms >= 0),
    occupied_rooms INTEGER NOT NULL CHECK (occupied_rooms >= 0),
    guests INTEGER NOT NULL CHECK (guests >= 0),
    CHECK (occupied_rooms <= available_rooms),
    PRIMARY KEY (sensor_id, timestamp)
);

CREATE TABLE IF NOT EXISTS sparkcity.fiscal_data (
    sensor_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    location_lat DOUBLE PRECISION NOT NULL CHECK (location_lat BETWEEN -90 AND 90),
    location_lon DOUBLE PRECISION NOT NULL CHECK (location_lon BETWEEN -180 AND 180),
    expense DOUBLE PRECISION NOT NULL CHECK (expense >= 0),
    revenue DOUBLE PRECISION NOT NULL CHECK (revenue >= 0),
    PRIMARY KEY (sensor_id, timestamp)
);

COMMIT;
