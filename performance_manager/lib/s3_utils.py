import os
from typing import Optional, List, Tuple, Union, Sequence, Iterator

import boto3
import pandas
import pyarrow.parquet as pq
from pyarrow import fs

from .logging_utils import ProcessLogger
import logging


def read_parquet(
    filename: Union[str, List[str]],
    columns: Union[List[str], slice] = slice(None),
    filters: Optional[Union[Sequence[Tuple], Sequence[List[Tuple]]]] = None,
) -> pandas.core.frame.DataFrame:
    """
    read parquet file or files from s3 and return it as a pandas dataframe
    """
    process_logger = ProcessLogger("read_parquet", filename=filename)

    try:
        active_fs = fs.S3FileSystem()
        if isinstance(filename, list):
            to_load = [f.replace("s3://", "") for f in filename]
        else:
            to_load = [filename.replace("s3://", "")]

        dataframe = (
            pq.ParquetDataset(to_load, filesystem=active_fs, filters=filters)
            .read_pandas()
            .to_pandas()
            .loc[:, columns]
        )

        process_logger.log_complete()

        return dataframe
    except Exception as exception:
        # log and re-raise
        process_logger.log_failure(exception)
        logging.exception(exception)
        raise exception


def file_list_from_s3(bucket_name: str, file_prefix: str) -> Iterator[str]:
    """
    generate filename, filesize tuples for every file in an s3 bucket

    :param bucket_name: the name of the bucket to look inside of
    :param file_prefix: prefix for files to generate

    :yield filename, filesize tuples from inside of the bucket
    """
    s3_client = boto3.client("s3")
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket_name, Prefix=file_prefix)
    for page in pages:
        if page["KeyCount"] == 0:
            continue
        for obj in page["Contents"]:
            # skip if this object is a "directory"
            if obj["Size"] == 0:
                continue
            uri = os.path.join("s3://", bucket_name, obj["Key"])
            yield uri
