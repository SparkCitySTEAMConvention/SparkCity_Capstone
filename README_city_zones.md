# City Zones exploration and enrichment: teach-back

My assignment in SparkCity is to explore the city zones reference data and use
it to add zone information to traffic readings. My work is in
[Day1_city_zones.ipynb](notebooks/Day1_city_zones.ipynb) on the
`pair-a-city-zones` branch.

## 1. What data am I working with?

[city_zones.csv](data/raw/city_zones.csv) contains **5 zones**. Each row describes
a rectangular area using latitude and longitude boundaries.

| Column | What it means | PySpark type |
| --- | --- | --- |
| `zone_id` | Identifier such as `ZONE_001` | `StringType` |
| `zone_name` | Readable name of the zone | `StringType` |
| `zone_type` | Commercial, residential, or industrial category | `StringType` |
| `lat_min` | Southern boundary | `DoubleType` |
| `lat_max` | Northern boundary | `DoubleType` |
| `lon_min` | Western boundary | `DoubleType` |
| `lon_max` | Eastern boundary | `DoubleType` |
| `population` | Population value assigned to the zone | `IntegerType` |

Negative longitude is expected in this dataset. For example, `-74.01` is less
than `-73.99` and lies farther west. These boxes are lab reference boundaries,
not verified neighborhood polygons.

[traffic_sensors.csv](data/raw/traffic_sensors.csv) contains **25 readings**.
The columns needed for mapping are `sensor_id`, `location_lat`, and
`location_lon`. A sensor can have readings at different timestamps, so a
repeated sensor ID does not by itself mean a duplicate reading.

## 2. How did I load the zones?

I used VS Code's notebook editor connected to the existing Docker Jupyter
server at `http://localhost:9503`. Python runs in Docker while I work in VS Code.
The Spark session connects to `spark://spark-master:7077`.

The notebook was renamed from `nday1.ipynb` to `Day1_city_zones.ipynb`.
We reused its existing Spark initialization and City Zones loading code.

The notebook kernel was working in `/home/jovyan/work/notebooks`, so the
original `data/raw` path pointed to the wrong folder. We corrected it to:

```python
data_dir = "../data/raw"
```

`..` means go up one directory. This path assumes the kernel is working in
the notebooks directory, as it was in this session.

The essential loading code is:

```python
zones_df = (
    spark.read
    .option("header", "true")
    .option("inferSchema", "true")
    .csv(f"{data_dir}/city_zones.csv")
)

zones_df.show(5, truncate=False)
zones_df.printSchema()
print(zones_df.count())
```

My explanation of each step:

- `spark` is the SparkSession: my entry point for working with Spark data.
- `zones_df` is a DataFrame: a table with named columns and a schema.
- `header=true` uses the first CSV row as column names.
- `inferSchema=true` asks Spark to infer types from the values. We have not
  enforced an explicit schema.
- `show()` displays rows; `truncate=False` keeps long names visible.
- `printSchema()` displays column types and whether nulls are allowed.
- `count()` counts rows. The result was **5**.

`nullable = true` means a column allows nulls; it does not prove that nulls
exist. Also, Spark displaying `40.7100` as `40.71` does not change its numeric value.

## 3. What quality checks did I perform?

We added small, read-only checks using `pyspark.sql.functions` as `F`.

| Check | How it works | Observed result |
| --- | --- | --- |
| Missing zone values | Filter each column with `isNull()` and count | 0 in every column |
| Duplicate zone IDs | `groupBy("zone_id").count()`, then filter counts above 1 | None |
| Invalid zone bounds | Check minimum is below maximum and coordinates are in range | None |
| Negative populations | Filter `population < 0` | None |
| Missing traffic coordinates | Check latitude or longitude for null | None |
| Out-of-range traffic coordinates | Check latitude within −90 to 90 and longitude within −180 to 180 | None |

An empty result table means no rows matched that problem condition. It does
not mean the original DataFrame became empty. These checks did not clean or
modify the source data. They also do not cover every possible quality issue,
such as blank strings, inconsistent category spelling, or geographic accuracy.

The traffic loading cell originally contained `YOUR_OPTIONS_HERE`. We replaced
that placeholder with the same header and schema-inference options used for zones.

Traffic coordinate ranges were:

| Coordinate | Minimum | Maximum |
| --- | ---: | ---: |
| Latitude | 40.7128 | 40.7614 |
| Longitude | −74.006 | −73.968 |

Valid coordinates do not necessarily fall inside one of our defined zones.

## 4. How does the zone mapping work?

We reused the notebook's existing `map_to_zones(sensor_df, zones_df)` function
and applied it directly to `traffic_df`:

```python
traffic_with_zones = map_to_zones(traffic_df, zones_df)
```

A reading matches a zone only when **all four** comparisons are true:

```python
join_condition = (
    (sensor_df.location_lat >= zones_df.lat_min)
    & (sensor_df.location_lat <= zones_df.lat_max)
    & (sensor_df.location_lon >= zones_df.lon_min)
    & (sensor_df.location_lon <= zones_df.lon_max)
)
```

This is an excerpt from inside the function, where `sensor_df` is its input
parameter. `&` combines the PySpark conditions, and the comparisons include
the edges of each box.

The function uses a **left join** to preserve every traffic reading, including
readings without a matching zone. The resulting DataFrame contains all original
traffic columns plus `zone_id`, `zone_name`, and `zone_type`.

## 5. What did the results teach me?

| Measurement | Result |
| --- | ---: |
| Input traffic readings | 25 |
| Output rows | 25 |
| Matched readings | 20 (80%) |
| Unmatched readings | 5 (20%) |
| Sensor locations matching multiple zones | 0 |

The observed mappings were:

| Sensor | Matched zone |
| --- | --- |
| `SENSOR_001` | `ZONE_001` — Downtown Manhattan |
| `SENSOR_002` | `ZONE_002` — Midtown East |
| `SENSOR_003` | `ZONE_003` — Upper East Side |
| `SENSOR_004` | No match |
| `SENSOR_005` | `ZONE_005` — Long Island City |

All five unmatched readings belong to `SENSOR_004`, at `(40.7505, -73.9972)`.
Its coordinates are valid but outside the defined boxes. Null zone fields are
therefore an expected mapping result. We kept those readings without forcing
them into a zone.

`ZONE_003` and `ZONE_004` overlap, but no current traffic location matches both.
Future readings in the overlap could produce multiple output rows per reading.
Shared edges can also create multiple matches because our bounds are inclusive.
A left join preserves input readings; it does **not** guarantee an unchanged
row count when multiple matches exist.

To check for multiple matches, we grouped by sensor ID and coordinates and
counted distinct `zone_id` values. This avoids mistaking repeated readings of
the same location for multiple zone matches. We have not implemented a rule
for choosing between overlapping zones.

## 6. How did I summarize readings by zone?

We created `zone_summary` from `traffic_with_zones`, grouping by `zone_id`,
`zone_name`, and `zone_type`. The notebook run produced:

| Zone | Reading count | Distinct sensor count |
| --- | ---: | ---: |
| Null (unmatched) | 5 | 1 |
| `ZONE_001` — Downtown Manhattan | 5 | 1 |
| `ZONE_002` — Midtown East | 5 | 1 |
| `ZONE_003` — Upper East Side | 5 | 1 |
| `ZONE_005` — Long Island City | 5 | 1 |

The reading counts sum to **25**, matching the mapped output row count.
`ZONE_004` is absent because no traffic readings matched it. This summary groups
existing readings; it does not automatically add zones with zero readings.

The key PySpark concepts are:

- `groupBy()` puts rows with the same zone fields into a group. Null zone
  fields form the unmatched group.
- `agg()` calculates summaries for each group.
- `F.count("*")` counts every row, including unmatched readings with null zone
  fields. Counting `zone_id` instead would exclude those null values.
- `F.countDistinct("sensor_id")` counts distinct non-null sensor IDs, so repeated
  readings from one sensor count as one sensor in that group.
- `alias()` gives the summary columns readable names.
- `orderBy()` sorts the displayed groups, and `F.sum("reading_count")` totals
  the summary's row counts.

My teach-back: “I counted readings separately from sensors because one sensor
reports repeatedly. Four zones each had five readings from one sensor, and the
five readings from SENSOR_004 stayed visible in the unmatched group.”

These are counts of mapped output rows. If future readings match multiple
zones, they can contribute to multiple groups; this summary does not resolve
overlap or guarantee unique input-reading counts across zones.

## 7. What did the boundary and overlap examples prove?

We created five made-up points in `example_locations` and passed them to the
same `map_to_zones()` function. These examples are separate from the raw traffic
data and do not change `traffic_with_zones`.

| Example | Latitude | Longitude | Observed matches |
| --- | ---: | ---: | --- |
| `inside` | 40.715 | −74.000 | `ZONE_001` |
| `boundary` | 40.710 | −74.010 | `ZONE_001` |
| `overlap` | 40.752 | −73.975 | `ZONE_003` and `ZONE_004` |
| `shared_edge` | 40.760 | −73.980 | `ZONE_004` and `ZONE_005` |
| `outside` | 40.700 | −74.020 | No match; retained with null zone fields |

The executed cell returned **5 input points and 7 output rows**. Both the
overlap point and the shared-edge point produced two matches. The boundary
corner was included because the comparisons use `>=` and `<=`.

My teach-back: “A left join preserves every input reading, but not necessarily
the input row count. Our mapping returns every matching zone. Inclusive edges
and overlapping boxes can therefore produce more than one row per reading.”

### Python-version limitation encountered

The first version used `spark.createDataFrame()` with a Python list. Execution
failed because the driver was running **Python 3.10** and the workers were
running **Python 3.8**. That operation required Python execution on the workers,
which exposed the incompatible minor versions.

We changed only the example cell to use `spark.sql()` with SQL `VALUES`, casting
the coordinates to `DOUBLE`. This builds the example table without worker-side
Python execution and allowed this checkpoint to succeed.

This is a workaround for this example, **not an environment fix**. The Python
version mismatch remains and can affect other operations requiring Python on
the workers. The team will need to align the driver and worker Python versions
before relying on those operations. No Docker or infrastructure files were
changed for this checkpoint.

## 8. How can I repeat this checkpoint?

Open the notebook in VS Code and select the Python kernel from the existing
Jupyter server at `http://localhost:9503`. With the Docker environment running,
run these cells in order. Search by their opening text because cell positions
can change as the notebook is edited.

| Current cell position | Opening text or purpose |
| --- | --- |
| 3 | `# Import required libraries` |
| 6 | `# TODO: Create Spark session` |
| 14 | `# Define data directory` |
| 15 | `# TODO: Load city zones reference data` |
| 16 | `# City Zones: basic quality checks` |
| 17 | `# TODO: Load traffic sensors data` |
| 18 | `# City Zones: inspect traffic coordinates before mapping` |
| 43 | `def map_to_zones(sensor_df, zones_df):` |
| 44 | `# City Zones: map traffic readings and check the results` |
| 45 | Markdown: City Zones mapping findings |
| 46 | `# City Zones: summarize readings by zone` |
| 47 | `# City Zones: map example coordinates` |

Positions count both Markdown and code cells, not the execution numbers shown
in brackets. Run these selected cells instead of **Run All**, which includes
other assignments and unfinished exercises. After changing the data directory
cell, rerun it before rerunning any loading cells.

## 9. My teach-back summary

“I loaded five city zones and checked their IDs, coordinates, and populations.
I then inspected 25 traffic readings and used each reading's latitude and
longitude to find matching zone boxes. A left join added zone information while
retaining readings outside those boxes. Twenty readings matched; five readings
from SENSOR_004 did not. None matched multiple zones in this dataset, but the
reference boxes overlap, so future data could behave differently.”

The next checkpoint could be reviewing the unmatched-reading and overlap
policies with the team before adding more behavior. This work did not add
cleaning, PostgreSQL loading, or infrastructure changes for the assignment.
Nothing was pushed or merged.
