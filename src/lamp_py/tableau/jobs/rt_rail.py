import os
import datetime

import pyarrow
import pyarrow.parquet as pq
import pyarrow.compute as pc
import pyarrow.dataset as pd
import sqlalchemy as sa

from lamp_py.tableau.hyper import HyperJob
from lamp_py.aws.s3 import download_file
from lamp_py.postgres.postgres_utils import DatabaseManager
from lamp_py.runtime_utils.process_logger import ProcessLogger


class HyperRtRail(HyperJob):
    """HyperJob for LAMP RT Rail data"""

    def __init__(self) -> None:
        HyperJob.__init__(
            self,
            hyper_file_name="LAMP_ALL_RT_fields.hyper",
            remote_parquet_path=f"s3://{os.getenv('PUBLIC_ARCHIVE_BUCKET')}/lamp/tableau/rail/LAMP_ALL_RT_fields.parquet",
            lamp_version="1.1.4",
        )
        self.table_query = (
            "SELECT"
            "   date(vt.service_date::text) as service_date"
            "   , vt.service_date::text::timestamp + make_interval(secs => vt.start_time) as start_datetime"
            "   , vt.service_date::text::timestamp + make_interval(secs => vt.static_start_time) as static_start_datetime"
            "   , ve.stop_sequence"
            "   , ve.canonical_stop_sequence"
            "   , prev_ve.canonical_stop_sequence as previous_canonical_stop_sequence"
            "   , ve.sync_stop_sequence"
            "   , prev_ve.sync_stop_sequence as previous_sync_stop_sequence"
            "   , ve.stop_id"
            "   , prev_ve.stop_id as previous_stop_id"
            "   , ve.parent_station"
            "   , prev_ve.parent_station as previous_parent_station"
            "   , ss.stop_name as stop_name"
            "   , prev_ss.stop_name as previous_stop_name"
            "   , TIMEZONE('America/New_York', TO_TIMESTAMP(ve.vp_move_timestamp)) as previous_stop_departure_datetime"
            "   , TIMEZONE('America/New_York', TO_TIMESTAMP(COALESCE(ve.vp_stop_timestamp,  ve.tu_stop_timestamp))) as stop_arrival_datetime"
            "   , TIMEZONE('America/New_York', TO_TIMESTAMP(next_ve.vp_move_timestamp)) as stop_departure_datetime"
            "   , extract(epoch FROM (TIMEZONE('America/New_York', TO_TIMESTAMP(ve.vp_move_timestamp)) - vt.service_date::text::timestamp))::int as previous_stop_departure_sec"
            "   , extract(epoch FROM (TIMEZONE('America/New_York', TO_TIMESTAMP(COALESCE(ve.vp_stop_timestamp,  ve.tu_stop_timestamp))) - vt.service_date::text::timestamp))::int as stop_arrival_sec"
            "   , extract(epoch FROM (TIMEZONE('America/New_York', TO_TIMESTAMP(next_ve.vp_move_timestamp)) - vt.service_date::text::timestamp))::int as stop_departure_sec"
            "   , vt.direction_id::int"
            "   , vt.route_id"
            "   , vt.branch_route_id"
            "   , vt.trunk_route_id"
            "   , vt.start_time"
            "   , vt.vehicle_id"
            "   , vt.stop_count"
            "   , vt.trip_id"
            "   , vt.vehicle_label"
            "   , vt.vehicle_consist"
            "   , vt.direction"
            "   , vt.direction_destination"
            "   , vt.static_trip_id_guess"
            "   , vt.static_start_time"
            "   , vt.static_stop_count"
            "   , vt.first_last_station_match as exact_static_trip_match"
            "   , vt.static_version_key"
            "   , ve.travel_time_seconds"
            "   , ve.dwell_time_seconds"
            "   , ve.headway_trunk_seconds"
            "   , ve.headway_branch_seconds"
            " FROM "
            "   vehicle_events ve"
            " LEFT JOIN "
            "   vehicle_trips vt"
            " ON "
            "   ve.pm_trip_id = vt.pm_trip_id"
            " LEFT JOIN "
            " ("
            "   SELECT "
            "       DISTINCT "
            "       direction_id "
            "       , route_id "
            "       , parent_station "
            "       , static_version_key "
            "       , true as drop_flag "
            "   FROM "
            "       ( "
            "       SELECT "
            "           canon_trips.direction_id "
            "           , CASE WHEN canon_trips.trunk_route_id = 'Green' THEN canon_trips.route_id ELSE canon_trips.trunk_route_id END as route_id "
            "           , static_stops.parent_station "
            "           , ROW_NUMBER() OVER (PARTITION BY canon_trips.static_version_key,canon_trips.direction_id,canon_trips.route_id ORDER BY static_stop_times.stop_sequence) as stop_sequence "
            "           , canon_trips.static_version_key "
            "       FROM "
            "           ( "
            "           SELECT "
            "               DISTINCT ON (coalesce(static_trips.branch_route_id,static_trips.trunk_route_id),static_route_patterns.direction_id,static_route_patterns.static_version_key) "
            "               static_route_patterns.direction_id as direction_id "
            "               , static_route_patterns.representative_trip_id as representative_trip_id "
            "               , static_trips.trunk_route_id as trunk_route_id "
            "               , coalesce(static_trips.branch_route_id, static_trips.trunk_route_id) as route_id "
            "               , static_route_patterns.static_version_key as static_version_key "
            "           FROM "
            "               static_route_patterns "
            "           JOIN static_trips on "
            "               static_route_patterns.representative_trip_id = static_trips.trip_id "
            "               AND static_route_patterns.static_version_key = static_trips.static_version_key "
            "           JOIN static_routes on "
            "               static_routes.route_id = static_trips.route_id "
            "               AND static_routes.static_version_key = static_trips.static_version_key "
            "           WHERE "
            "               static_routes.route_type < 2 "
            "               AND (static_route_patterns.route_pattern_typicality = 1 "
            "                   or static_route_patterns.route_pattern_typicality = 5) "
            "           order by "
            "               coalesce(static_trips.branch_route_id, static_trips.trunk_route_id), "
            "               static_route_patterns.direction_id, "
            "               static_route_patterns.static_version_key, "
            "               static_route_patterns.route_pattern_typicality desc) as canon_trips "
            "       JOIN static_stop_times on "
            "           canon_trips.representative_trip_id = static_stop_times.trip_id "
            "           AND canon_trips.static_version_key = static_stop_times.static_version_key "
            "       JOIN static_stops on "
            "           static_stop_times.stop_id = static_stops.stop_id "
            "           AND static_stop_times.static_version_key = static_stops.static_version_key ) as drop_station "
            "   WHERE "
            "       drop_station.stop_sequence = 1 "
            " ) drop_join"
            " ON "
            "   drop_join.direction_id = vt.direction_id "
            "   AND drop_join.route_id = vt.route_id "
            "   AND drop_join.parent_station = ve.parent_station  "
            "   AND drop_join.static_version_key = vt.static_version_key "
            " LEFT JOIN "
            "   vehicle_events prev_ve"
            " ON "
            "   ve.pm_event_id = prev_ve.next_trip_stop_pm_event_id"
            " LEFT JOIN "
            "   vehicle_events next_ve"
            " ON "
            "   ve.pm_event_id = next_ve.previous_trip_stop_pm_event_id"
            " LEFT JOIN "
            "   static_stops ss"
            " ON "
            "   ve.stop_id = ss.stop_id"
            "   AND vt.static_version_key = ss.static_version_key"
            " LEFT JOIN "
            "   static_stops prev_ss"
            " ON "
            "   prev_ve.stop_id = prev_ss.stop_id"
            "   AND vt.static_version_key = prev_ss.static_version_key"
            " LEFT JOIN "
            "   static_routes sr"
            " ON "
            "   vt.route_id = sr.route_id"
            "   AND vt.static_version_key = sr.static_version_key"
            " WHERE "
            "   sr.route_type < 2"
            "   AND drop_join.drop_flag IS NULL "
            "   AND ("
            "       ve.vp_stop_timestamp IS NOT null"
            "       OR ve.vp_move_timestamp IS NOT null"
            "   )"
            "   %s"
            " ORDER BY "
            "   ve.service_date, vt.vehicle_id, vt.start_time"
            ";"
        )
        # based on testing, batch_size of 1024 * 256 should result in a maximum
        # memory usage of ~9GB for this dataset.
        #
        # this memory usage profile is based on the current schema of this
        # dataset and should be revisited if schema changes are made
        #
        # batch_size/row group size of input parquet files can also impact
        # memory usage of batched ParquetWriter operations
        self.ds_batch_size = 1024 * 256
        self.db_parquet_path = "/tmp/db_local.parquet"

    @property
    def parquet_schema(self) -> pyarrow.schema:
        return pyarrow.schema(
            [
                ("service_date", pyarrow.date32()),
                ("start_datetime", pyarrow.timestamp("us")),
                ("static_start_datetime", pyarrow.timestamp("us")),
                ("stop_sequence", pyarrow.int16()),
                ("canonical_stop_sequence", pyarrow.int16()),
                ("previous_canonical_stop_sequence", pyarrow.int16()),
                ("sync_stop_sequence", pyarrow.int16()),
                ("previous_sync_stop_sequence", pyarrow.int16()),
                ("stop_id", pyarrow.string()),
                ("previous_stop_id", pyarrow.string()),
                ("parent_station", pyarrow.string()),
                ("previous_parent_station", pyarrow.string()),
                ("stop_name", pyarrow.string()),
                ("previous_stop_name", pyarrow.string()),
                ("previous_stop_departure_datetime", pyarrow.timestamp("us")),
                ("stop_arrival_datetime", pyarrow.timestamp("us")),
                ("stop_departure_datetime", pyarrow.timestamp("us")),
                ("previous_stop_departure_sec", pyarrow.int64()),
                ("stop_arrival_sec", pyarrow.int64()),
                ("stop_departure_sec", pyarrow.int64()),
                ("direction_id", pyarrow.int8()),
                ("route_id", pyarrow.string()),
                ("branch_route_id", pyarrow.string()),
                ("trunk_route_id", pyarrow.string()),
                ("start_time", pyarrow.int64()),
                ("vehicle_id", pyarrow.string()),
                ("stop_count", pyarrow.int16()),
                ("trip_id", pyarrow.string()),
                ("vehicle_label", pyarrow.string()),
                ("vehicle_consist", pyarrow.string()),
                ("direction", pyarrow.string()),
                ("direction_destination", pyarrow.string()),
                ("static_trip_id_guess", pyarrow.string()),
                ("static_start_time", pyarrow.int64()),
                ("static_stop_count", pyarrow.int64()),
                ("exact_static_trip_match", pyarrow.bool_()),
                ("static_version_key", pyarrow.int64()),
                ("travel_time_seconds", pyarrow.int32()),
                ("dwell_time_seconds", pyarrow.int32()),
                ("headway_trunk_seconds", pyarrow.int32()),
                ("headway_branch_seconds", pyarrow.int32()),
            ]
        )

    def create_parquet(self, db_manager: DatabaseManager) -> None:
        create_query = self.table_query % ""

        if os.path.exists(self.local_parquet_path):
            os.remove(self.local_parquet_path)

        db_manager.write_to_parquet(
            select_query=sa.text(create_query),
            write_path=self.local_parquet_path,
            schema=self.parquet_schema,
            batch_size=self.ds_batch_size,
        )

    # pylint: disable=R0914
    # there are a lot of vars in here used for logging and it pushes the total
    # method variables past the threshold.
    def update_parquet(self, db_manager: DatabaseManager) -> bool:
        process_logger = ProcessLogger("update_rt_rail_parquet")
        process_logger.log_start()

        download_file(
            object_path=self.remote_parquet_path,
            file_name=self.local_parquet_path,
        )

        max_stats = self.max_stats_of_parquet()

        max_start_date: datetime.date = max_stats["service_date"]
        # subtract additional day incase of early spurious service_date record
        max_start_date -= datetime.timedelta(days=1)

        update_query = self.table_query % (
            f" AND ve.service_date >= {max_start_date.strftime('%Y%m%d')} ",
        )

        db_manager.write_to_parquet(
            select_query=sa.text(update_query),
            write_path=self.db_parquet_path,
            schema=self.parquet_schema,
            batch_size=self.ds_batch_size,
        )

        check_filter = pc.field("service_date") >= max_start_date
        if pd.dataset(self.db_parquet_path).count_rows() == pd.dataset(
            self.local_parquet_path
        ).count_rows(filter=check_filter):
            process_logger.add_metadata(new_data=False)
            process_logger.log_complete()
            # No new records from database, no upload required
            return False

        process_logger.add_metadata(new_data=True)

        # update downloaded parquet file with filtered service_date
        old_filter = pc.field("service_date") < max_start_date
        old_batches = pd.dataset(self.local_parquet_path).to_batches(
            filter=old_filter, batch_size=self.ds_batch_size
        )
        filter_path = "/tmp/filter_local.parquet"

        old_batch_count = 0
        old_batch_rows = 0
        old_batch_bytes = 0

        with pq.ParquetWriter(
            filter_path, schema=self.parquet_schema
        ) as writer:
            for batch in old_batches:
                old_batch_count += 1
                old_batch_rows += batch.num_rows
                old_batch_bytes += batch.nbytes
                process_logger.add_metadata(
                    old_batch_count=old_batch_count,
                    old_batch_rows=old_batch_rows,
                    old_batch_bytes=old_batch_bytes,
                )

                writer.write_batch(batch)
        os.replace(filter_path, self.local_parquet_path)

        joined_dataset = [
            pd.dataset(self.local_parquet_path),
            pd.dataset(self.db_parquet_path),
        ]

        combine_parquet_path = "/tmp/combine.parquet"
        combine_batches = pd.dataset(
            joined_dataset,
            schema=self.parquet_schema,
        ).to_batches(batch_size=self.ds_batch_size)

        combine_batch_count = 0
        combine_batch_rows = 0
        combine_batch_bytes = 0

        with pq.ParquetWriter(
            combine_parquet_path, schema=self.parquet_schema
        ) as writer:
            for batch in combine_batches:
                combine_batch_count += 1
                combine_batch_rows += batch.num_rows
                combine_batch_bytes += batch.nbytes
                process_logger.add_metadata(
                    combine_batch_count=combine_batch_count,
                    combine_batch_rows=combine_batch_rows,
                    combine_batch_bytes=combine_batch_bytes,
                )

                writer.write_batch(batch)

        os.replace(combine_parquet_path, self.local_parquet_path)
        os.remove(self.db_parquet_path)

        process_logger.log_complete()
        return True

    # pylint: enable=R0914
