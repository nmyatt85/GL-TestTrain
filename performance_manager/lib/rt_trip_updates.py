from typing import Optional, Union, List, Dict, Any

import logging
import pathlib
import pandas
import numpy

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from .s3_utils import read_parquet
from .gtfs_utils import start_time_to_seconds, add_event_hash_column
from .postgres_utils import TripUpdateEvents, MetadataLog


def get_tu_dataframe(to_load: Union[str, List[str]]) -> pandas.DataFrame:
    """
    return a dataframe from a trip updates parquet file (or list of files)
    with expected columns
    """
    trip_update_columns = [
        "timestamp",
        "stop_time_update",
        "direction_id",
        "route_id",
        "start_date",
        "start_time",
        "vehicle_id",
    ]
    trip_update_filters = [
        ("direction_id", "in", (0, 1)),
        ("timestamp", ">", 0),
        ("route_id", "!=", "None"),
        ("start_date", "!=", "None"),
        ("start_time", "!=", "None"),
        ("vehicle_id", "!=", "None"),
    ]

    return read_parquet(
        to_load, columns=trip_update_columns, filters=trip_update_filters
    )


def explode_stop_time_update(row: pandas.Series) -> Optional[List[dict]]:
    """
    function to be used with pandas `apply` dataframe method
    explode nested list of dicts in stop_time_update column
    """
    append_dict = {
        "timestamp": row["timestamp"],
        "direction_id": row["direction_id"],
        "route_id": row["route_id"],
        "start_date": row["start_date"],
        "start_time": row["start_time"],
        "vehicle_id": row["vehicle_id"],
    }
    return_list: List[Dict[str, Any]] = []
    for record in row["stop_time_update"]:
        try:
            arrival_time = int(record["arrival"]["time"])
        except (TypeError, KeyError):
            continue
        if (
            arrival_time - row["timestamp"] < 0
            or arrival_time - row["timestamp"] > 120
        ):
            continue
        append_dict.update(
            {
                "stop_id": record.get("stop_id"),
                "stop_sequence": record.get("stop_sequence"),
                "timestamp_start": arrival_time,
            }
        )
        return_list.append(append_dict.copy())

    if len(return_list) == 0:
        return None

    return return_list


def unwrap_tu_dataframe(events: pandas.DataFrame) -> pandas.DataFrame:
    """
    unwrap and explode trip updates records from parquet files
    parquet files contain stop_time_update field that is saved as list of dicts
    stop_time_update must have fields extracted and flattened to create
    predicted trip update stop events
    """

    # store start_date as int64
    events["start_date"] = pandas.to_numeric(events["start_date"]).astype(
        "int64"
    )

    # store direction_id as int64
    events["direction_id"] = pandas.to_numeric(events["direction_id"]).astype(
        "int64"
    )

    # store start_time as seconds from start of day int64
    events["start_time"] = (
        events["start_time"].apply(start_time_to_seconds).astype("int64")
    )

    # expand and filter stop_time_update column
    # this will return a Series with values being list of dicts
    events = events.apply(explode_stop_time_update, axis=1).dropna()

    # transform Series of list of dicts into dataframe
    events = pandas.json_normalize(events.explode())

    # is_moving column to indicate all stop events
    # needed for later join with vehicle_position_event by hash
    events["is_moving"] = False
    events["pk_id"] = None

    # add hash column, hash should be consistent across trip_update and
    # vehicle_position events
    events = add_event_hash_column(events).sort_values(by=["hash", "timestamp"])

    # after sort, drop all duplicates by hash, keep last record
    # last record will be most recent arrival time prediction for event
    events = events.drop_duplicates(subset=["hash"], keep="last")

    # after sort and drop timestamp column no longer needed
    events = events.drop(columns=["timestamp"])

    return events


def merge_trip_update_events(
    new_events: pandas.DataFrame, session: sa.orm.session.sessionmaker
) -> None:
    """
    merge new trip update evetns with existing events found in database
    merge performed on hash of records
    """
    hash_list = new_events["hash"].tolist()
    get_db_events = sa.select(
        (
            TripUpdateEvents.pk_id,
            TripUpdateEvents.hash,
            TripUpdateEvents.timestamp_start,
        )
    ).where(TripUpdateEvents.hash.in_(hash_list))
    with session.begin() as curosr:  # type: ignore
        merge_events = pandas.concat(
            [
                pandas.DataFrame(
                    [r._asdict() for r in curosr.execute(get_db_events)]
                ),
                new_events,
            ]
        ).sort_values(by=["hash", "timestamp_start"])

    # Identify records that are continuing from existing db
    # If such records are found, update timestamp_end with latest value
    first_of_consecutive_events = (
        merge_events["hash"] - merge_events["hash"].shift(-1) == 0
    )
    last_of_consecutive_events = (
        merge_events["hash"] - merge_events["hash"].shift(1) == 0
    )
    merge_events["timestamp_start"] = numpy.where(
        first_of_consecutive_events,
        merge_events["timestamp_start"].shift(-1),
        merge_events["timestamp_start"],
    )

    existing_was_updated_mask = (
        ~(merge_events["pk_id"].isna()) & first_of_consecutive_events
    )

    existing_to_del_mask = (
        ~(merge_events["pk_id"].isna()) & last_of_consecutive_events
    )

    logging.info(
        "Size of existing update df: %d", existing_was_updated_mask.sum()
    )
    logging.info("Size of existing delete df: %d", existing_to_del_mask.sum())

    # new events that will be inserted into db table
    new_to_insert_mask = (
        merge_events["pk_id"].isna()
    ) & ~last_of_consecutive_events
    logging.info("Size of new insert df: %d", new_to_insert_mask.sum())

    # DB UPDATE operation
    if existing_was_updated_mask.sum() > 0:
        update_db_events = sa.update(TripUpdateEvents.__table__).where(
            TripUpdateEvents.pk_id == sa.bindparam("b_pk_id")
        )
        with session.begin() as cursor:  # type: ignore
            cursor.execute(
                update_db_events,
                merge_events.rename(columns={"pk_id": "b_pk_id"})
                .loc[existing_was_updated_mask, ["b_pk_id", "timestamp_start"]]
                .to_dict(orient="records"),
            )

    # DB DELETE operation
    if existing_to_del_mask.sum() > 0:
        delete_db_events = sa.delete(TripUpdateEvents.__table__).where(
            TripUpdateEvents.pk_id.in_(
                merge_events.loc[existing_to_del_mask, "pk_id"]
            )
        )
        with session.begin() as cursor:  # type: ignore
            cursor.execute(delete_db_events)

    # DB INSERT operation
    if new_to_insert_mask.sum() > 0:
        insert_cols = list(set(merge_events.columns) - {"pk_id"})
        with session.begin() as cursor:  # type: ignore
            cursor.execute(
                sa.insert(TripUpdateEvents.__table__),
                merge_events.loc[new_to_insert_mask, insert_cols].to_dict(
                    orient="records"
                ),
            )


def process_trip_updates(sql_session: sessionmaker) -> None:
    """
    process trip updates parquet files from metadataLog table
    """

    # pull list of objects that need processing from metadata table
    # group objects by similar hourly folders
    read_md_log = sa.select((MetadataLog.pk_id, MetadataLog.path)).where(
        (MetadataLog.processed == sa.false())
        & (MetadataLog.path.contains("RT_TRIP_UPDATES"))
    )
    with sql_session.begin() as cursor:  # type: ignore
        paths_to_load: dict[str, dict[str, list]] = {}
        for path_id, path in cursor.execute(read_md_log):
            path = pathlib.Path(path)
            if path.parent not in paths_to_load:
                paths_to_load[path.parent] = {"ids": [], "paths": []}
            paths_to_load[path.parent]["ids"].append(path_id)
            paths_to_load[path.parent]["paths"].append(str(path))

    for folder_data in paths_to_load.values():
        ids = folder_data["ids"]
        paths = folder_data["paths"]

        try:
            new_events = get_tu_dataframe(paths)
            new_events = unwrap_tu_dataframe(new_events)
            merge_trip_update_events(new_events=new_events, session=sql_session)
        except Exception as e:
            logging.info("Error Processing Trip Updates")
            logging.exception(e)
        else:
            update_md_log = (
                sa.update(MetadataLog.__table__)
                .where(MetadataLog.pk_id.in_(ids))
                .values(processed=1)
            )
            with sql_session.begin() as cursor:  # type: ignore
                cursor.execute(update_md_log)
