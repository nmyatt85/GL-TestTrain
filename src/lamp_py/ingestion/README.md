# Ingestion

Ingestion is an application to transform and aggregate GTFS-RT and GTFS Static files into parquet files for storage in AWS S3 buckets.

## Application Operation

Ingestion operates with a chronologic event loop with a 5 minute delay between each iteration.

Ingestion connects to the [Performance Manager](../performance_manager/README.md) application via the `metadata_log` table of the Metadata RDS. When Ingestion creates a new parquet file, the S3 path of that file is written to the `metadata_log` table for Performance Manager to process.

For each event loop, GTFS Static files are processed prior to any GTFS-RT files, when available.

## Event Loop Summary

1. List all files from `incoming` S3 bucket
2. Bucket files into applicable `Converter` class
3. Start `converter` loop of each `Converter` class, creating parquet files
4. Write parquet file to S3 Bucket
5. Write S3 path of parquet file to `metadata_log` table for Performance Manager
6. Move successfully processed `incoming` files to `archive` bucket
7. Move un-successfully processed `incoming` files to `error` bucket

# GTFS Static

[GTFS Static](https://www.mbta.com/developers/gtfs) Zip files are generated by MBTA for internal and external distribution. When a new GTFS Static Zip file is generated, the CTD [Delta](https://github.com/mbta/delta) application writes it to an AWS S3 bucket for use by LAMP.

This application converts GTFS Zip files, saved on S3 by Delta, to partitioned parquet files that are also saved to an S3 bucket. This is done with the [GTFS Converter Class](./convert_gtfs.py).

GTFS Static parquet files are written to S3 with the following partitioning:

* [GTFS File Type](https://github.com/mbta/gtfs-documentation/blob/master/reference/gtfs.md#gtfs-files)
* timestamp = modified (UNIX) timestamp of [feed_info.txt](https://github.com/mbta/gtfs-documentation/blob/master/reference/gtfs.md#feed_infotxt) file in ZIP archive

# GTFS-RT Data

[GTFS-realtime](https://www.mbta.com/developers/gtfs-realtime) (GTFS-RT) is provided by MBTA as an industry standard for distributing realtime transit data. 

The CTD [Delta](https://github.com/mbta/delta) application is responsible for reading GTFS-RT updates from the MBTA [V3 API](https://www.mbta.com/developers/v3-api) and saving them to an AWS S3 Bucket, as gzipped JSON files, for use by LAMP.

This application aggregates gzipped GTFS-RT update files, saved on S3 by Delta, into partitioned parquet files that are also saved to an S3 bucket. The parquet files are partitioned by GTFS-RT feed type and grouped into hourly chunks. This is done with the [GTFS-RT Converter Class](./convert_gtfs_rt.py)

GTFS-RT parquet files are transformed and partitioned based on their `Converter Class` configuration:

* [Busloc Trip Updates](./config_busloc_trip.py)
* [Busloc Vehicle Positions](./config_busloc_vehicle.py)
* [Realtime Vehicle Positions](./config_rt_vehicle.py)
* [Realtime Trip Updates](./config_rt_trip.py)
* [Sevice Alerts](./config_rt_alerts.py)
