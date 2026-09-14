# Notebook inputs and outputs

Use the project's `.venv` kernel. Restart the kernel before **Run All** when switching notebooks or recovering from a failed Spark startup.

1. `Hakeem_day1.ipynb` reads the seven existing `data/raw` files. Its final export saves typed, validated Parquet datasets to a unique `data/processed/day1/<run>` directory. Traffic includes zone metadata and match counts. A completed manifest records file hashes, row counts and source provenance.
2. `Hakeem_day2.ipynb` selects the latest completed Day 1 run by default. Set `DAY1_RUN` in its setup cell to pin a specific run. Missing, changed or incomplete inputs fail explicitly. Day 2 writes quality reports, accepted datasets, quarantine records and outlier thresholds to `data/processed/day2/<run>`.
3. `Hakeem_day3.ipynb` reads a completed Day 2 run with the corrected Day 1 lineage. It verifies row counts, preserves original fields and traffic zone metadata, and exports features, daily traffic-zone aggregates, charts, correlations and trends. Coverage timestamps use the explicit Spark processing timezone. Rerun it to use newly cleaned data; set `DAY2_RUN` to pin a particular input.
4. `Hakeem_day4.ipynb` requires the corrected Day 3 lineage and flag-only Day 2 data for modeling. It records input hashes, retains traffic zones in alerts, checks saved-model inference without future labels, and exports validation/test metrics and measured cache costs. Set `DAY3_RUN` to pin an input; rerun to use updated features.

The Day 2 manifest preserves the existing fields expected by Day 3 and adds `day1_run` and `day1_manifest_sha256`. No previous run is overwritten or automatically refreshed. Only directories with a `manifest.json` marked `complete` should be used downstream.

Day 1 and Day 2 do not write S2. Day 1's optional connection check is disabled by default. Generated snapshots and reports are ignored by Git. Source measurement units and source timezone remain unconfirmed; parsing timestamps does not establish real-world timezone, and unit conversion requires explicit input.
