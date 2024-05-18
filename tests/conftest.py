"""
this file contains fixtures that are intended to be used across multiple test
files
"""

from typing import (
    Iterator,
    List,
    Optional,
    Union,
)

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pyarrow import fs
import pyarrow.dataset as pd


@pytest.fixture(autouse=True, name="get_pyarrow_dataset_patch")
def fixture_get_pyarrow_dataset_patch(
    monkeypatch: MonkeyPatch,
) -> Iterator[None]:
    """
    the aws.s3 function `_get_pyarrow_dataset` function reads parquet files from
    s3 and returns a pyarrow dataset. when testing on our github machines, we
    don't have access to s3, so all tests must be run against local files.
    monkeypatch the function to read from a local filepath.
    """

    def mock__get_pyarrow_dataset(
        filename: Union[str, List[str]],
        filters: Optional[pd.Expression] = None,
    ) -> pd.Dataset:
        active_fs = fs.LocalFileSystem()

        if isinstance(filename, list):
            to_load = filename
        else:
            to_load = [filename]

        if len(to_load) == 0:
            return pd.dataset([])

        ds = pd.dataset(to_load, filesystem=active_fs, partitioning="hive")
        if filters is not None:
            ds = ds.filter(filters)

        return ds

    monkeypatch.setattr(
        "lamp_py.aws.s3._get_pyarrow_dataset", mock__get_pyarrow_dataset
    )

    yield
