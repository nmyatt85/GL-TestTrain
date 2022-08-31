#!/usr/bin/env python

import argparse
import json
import logging
import os
import sys
import time

from typing import NamedTuple

from py_gtfs_rt_ingestion import ArgumentException
from py_gtfs_rt_ingestion import DEFAULT_S3_PREFIX
from py_gtfs_rt_ingestion import LambdaContext
from py_gtfs_rt_ingestion import LambdaDict
from py_gtfs_rt_ingestion import batch_files
from py_gtfs_rt_ingestion import file_list_from_s3
from py_gtfs_rt_ingestion import load_environment
from py_gtfs_rt_ingestion import get_psql_conn


logging.getLogger().setLevel("INFO")

DESCRIPTION = "Generate batches of json files that should be processed"


class BatchArgs(NamedTuple):
    """wrapper for arguments to main method"""

    filesize_threshold: int = 100 * 1_000 * 1_000
    s3_prefix: str = DEFAULT_S3_PREFIX
    print_events: bool = False
    dry_run: bool = False
    debug_rds_connection: bool = False


def parse_args(args: list[str]) -> dict:
    """
    parse input args from the command line. using them, generate an event
    lambdadict object and set environment variables.
    """
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument(
        "--s3-prefix",
        dest="s3_prefix",
        type=str,
        default=DEFAULT_S3_PREFIX,
        help="prefix to files in the mbta-gtfs-s3 bucket",
    )

    parser.add_argument(
        "--threshold",
        dest="filesize_threshold",
        type=int,
        default=100000,
        help="filesize threshold for batch sizes",
    )

    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="do not invoke ingest lambda function",
    )

    parser.add_argument(
        "--print-events",
        dest="print_events",
        action="store_true",
        help="print out each event as json to stdout",
    )

    return vars(parser.parse_args(args))


def main(batch_args: BatchArgs) -> None:
    """
    * get all of the files and their sizes from the import s3 bucket
    * convert them into batches of matching files
    * trigger the ingestion lambda async
    """
    try:
        s3_bucket = os.path.join(os.environ["INGEST_BUCKET"])
    except KeyError as e:
        raise ArgumentException("Missing S3 Bucket environment variable") from e

    start_time = time.time()
    logging.info("start=%s", "batch_files_lambda")

    file_list = file_list_from_s3(
        bucket_name=s3_bucket, file_prefix=batch_args.s3_prefix
    )

    total_bytes = 0
    total_files = 0
    events = []
    for batch in batch_files(file_list, batch_args.filesize_threshold):
        total_bytes += batch.total_size
        total_files += len(batch.filenames)
        events.append(batch.create_event())

        if not batch_args.dry_run:
            batch.trigger_lambda()

    if batch_args.print_events:
        logging.info(json.dumps(events, indent=2))

    logging.info(
        "complete=%s, duration=%.2f",
        "batch_files_lambda",
        time.time() - start_time,
    )


def lambda_handler(
    event: LambdaDict, context: LambdaContext  # pylint: disable=W0613
) -> None:
    """
    AWS Lambda Python handled function as described in AWS Developer Guide:
    https://docs.aws.amazon.com/lambda/latest/dg/python-handler.html
    :param event: The event dict sent by Amazon API Gateway that contains all of
            the request data.
    :param context: The context in which the function is called.
    :return: A response that is sent to Amazon API Gateway, to be wrapped into
             an HTTP response. The 'statusCode' field is the HTTP status code
             and the 'body' field is the body of the response.

    expected event structure is
    {
        s3_prefix: str
        filesize_threshold: int
    }

    batch files should all be of same ConfigType
    """
    logging.info("Processing event:\n%s", json.dumps(event, indent=2))
    logging.info("Context:\n%s", context)

    try:
        if len(set(event) - set(BatchArgs()._fields)) == 0:
            batch_args = BatchArgs(**event)
        else:
            batch_args = BatchArgs()

        if batch_args.debug_rds_connection:
            get_psql_conn()
        else:
            main(batch_args)
    except Exception as exception:
        logging.exception(
            "failed=%s, error_type=%s",
            "batch_files_lambda",
            type(exception).__name__,
        )


if __name__ == "__main__":
    load_environment()
    parsed_event = parse_args(sys.argv[1:])
    parsed_context = LambdaContext()
    lambda_handler(parsed_event, parsed_context)
