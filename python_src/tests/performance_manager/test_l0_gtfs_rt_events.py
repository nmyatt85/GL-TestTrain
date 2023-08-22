import os
import pathlib

from lamp_py.performance_manager.l0_rt_vehicle_positions import (
    get_vp_dataframe,
    transform_vp_datatypes,
)
from lamp_py.performance_manager.l0_rt_trip_updates import (
    get_and_unwrap_tu_dataframe,
)
from lamp_py.performance_manager.gtfs_utils import (
    add_missing_service_dates,
)

from ..test_resources import test_files_dir, csv_to_vp_parquet


def test_vp_missing_service_date(tmp_path: pathlib.Path) -> None:
    """
    test that missing service dates in gtfs-rt vehicle position files can be
    correctly backfilled.
    """
    csv_file = os.path.join(test_files_dir, "vp_missing_start_date.csv")

    parquet_folder = tmp_path.joinpath(
        "RT_VEHICLE_POSITIONS/year=2023/month=5/day=8/hour=11"
    )
    parquet_folder.mkdir(parents=True)
    parquet_file = str(parquet_folder.joinpath("flat_file.parquet"))

    csv_to_vp_parquet(csv_file, parquet_file)

    events = get_vp_dataframe(to_load=[parquet_file], route_ids=["Blue"])
    events = transform_vp_datatypes(events)

    # ensure that there are NaN service dates
    assert events["service_date"].hasnans

    # add the service dates that are missing
    events = add_missing_service_dates(
        events, timestamp_key="vehicle_timestamp"
    )

    # check that new service dates match existing and are numbers
    assert len(events["service_date"].unique()) == 1
    assert not events["service_date"].hasnans


def test_tu_missing_service_date() -> None:
    """
    test that trip update gtfs data with missing service dates can be processed
    correctly.
    """
    parquet_file = os.path.join(test_files_dir, "tu_missing_start_date.parquet")
    events = get_and_unwrap_tu_dataframe([parquet_file], route_ids=["Blue"])

    # check that NaN service dates exist from reading the file
    assert events["service_date"].hasnans

    events = add_missing_service_dates(
        events_dataframe=events, timestamp_key="timestamp"
    )

    # check that all service dates exist and are the same
    assert not events["service_date"].hasnans
    assert len(events["service_date"].unique()) == 1
