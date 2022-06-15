#!/usr/bin/env python

import argparse
import logging
import sys
from typing import NamedTuple
import os
import random
from multiprocessing import Pool
from collections.abc import Iterable

import boto3

from py_gtfs_rt_ingestion import file_list_from_s3

GTFS_BUCKET = "mbta-gtfs-s3"
DEV_INGEST_BUCKET = "mbta-ctd-dataplatform-dev-incoming"
DEV_EXPORT_BUCKET = "mbta-ctd-dataplatform-dev-springboard"
DEV_ARCHIVE_BUCKET = "mbta-ctd-dataplatform-dev-archive"
DEV_ERROR_BUCKET = "mbta-ctd-dataplatform-dev-error"
LAMP_PREFIX = "lamp/"

logging.basicConfig(level=logging.WARNING)


class SetupArgs(NamedTuple):
    """
    NamedTuple to hold Setup arguments
    """

    src_prefix: str
    objs_to_copy: int
    force_delete: bool


def parse_args(args: list[str]) -> SetupArgs:
    """
    parse input args from the command line and generate an event dict in the
    format the lambda handler is expecting
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--source-prefix",
        dest="src_prefix",
        type=str,
        default="",
        help="prefix of objects to move into dev environment",
    )

    parser.add_argument(
        "-n",
        "--num",
        dest="objs_to_copy",
        type=int,
        default=1_000,
        help="number of objects to move into dev environment",
    )

    parser.add_argument(
        "-f",
        dest="force_delete",
        default=False,
        action="store_true",
        help="delete objects from dev buckets without asking",
    )

    return SetupArgs(**vars(parser.parse_args(args)))


def del_objs(del_list: list[str], bucket: str) -> int:
    """
    Delete del_list of objects from bucket
    """
    s3_client = boto3.client("s3")
    delete_objs = {
        "Objects": [
            {"Key": uri.replace(f"s3://{bucket}/", "")} for uri in del_list
        ]
    }
    try:
        s3_client.delete_objects(
            Bucket=bucket,
            Delete=delete_objs,
        )
    except Exception as e:
        logging.exception(e)
        return 0
    return len(del_list)


def make_del_jobs(files: list[str], bucket: str) -> int:
    """
    Spin up Multiprocessing jobs to delete batches of objects
    """
    chunk = 750
    with Pool(os.cpu_count()) as pool:
        l_t = [
            (files[i : i + chunk], bucket) for i in range(0, len(files), chunk)
        ]
        results = pool.starmap_async(del_objs, l_t)
        del_count = sum(r for r in results.get())
    return del_count


def get_del_obj_list(bucket: str, uri_root: str) -> list[str]:
    """
    Return list of objects in bucket, removing uri_root object from return list
    """
    print(f"Checking for objects to delete in {uri_root}...")
    files_to_delete = []
    for (uri, _) in file_list_from_s3(bucket, LAMP_PREFIX):
        files_to_delete.append(uri)
    # Remove uri_root from list so that root directory is not deleted.
    files_to_delete.remove(uri_root)
    return sorted(files_to_delete, reverse=True)


def clear_dev_buckets(args: SetupArgs) -> None:
    """
    Clear all development buckets of objects
    """
    bucket_list = (
        DEV_INGEST_BUCKET,
        DEV_EXPORT_BUCKET,
        DEV_ARCHIVE_BUCKET,
        DEV_ERROR_BUCKET,
    )

    for bucket in bucket_list:
        action = None
        uri_root = f"s3://{os.path.join(bucket, LAMP_PREFIX)}"
        files_to_delete = get_del_obj_list(bucket, uri_root)
        if len(files_to_delete) == 0:
            print("No objects found... skipping bucket.")
        else:
            while action not in ("n", "no"):
                # Print list of bucket objects
                if action in ("list", "ls"):
                    print(f"/{'*' * 50}/")
                    for uri in files_to_delete:
                        print(f"{uri.replace(uri_root, '')}")
                    print(f"/{'*' * 50}/")
                # Proceed with object deletion
                elif action in ("y", "yes") or args.force_delete:
                    delete_count = make_del_jobs(files_to_delete, bucket)
                    # If not all objects deleted, retry
                    if delete_count < len(files_to_delete):
                        print(
                            f"Only {delete_count:,} of {len(files_to_delete):,}"
                            " deleted... will retry."
                        )
                        files_to_delete = get_del_obj_list(bucket, uri_root)
                    else:
                        print(f"All {len(files_to_delete)} deleted")
                        break

                print(
                    f"{len(files_to_delete):,} objects found, delete? "
                    "\n"
                    "yes(y) / no(n) / list(ls)"
                )
                action = input()


def copy_obj(prefix: str, num_to_copy: int) -> int:
    """
    Copy random objects from prefix to dev Ingest bucket
    """
    count_objs_to_pull = max(num_to_copy * 10, 1_000)
    uri_copy_set = set()
    src_uri_root = f"s3://{os.path.join(GTFS_BUCKET, prefix)}"
    skip_uri = "https_mbta_busloc_s3.s3.amazonaws.com_prod_TripUpdates_enhanced"
    print(
        f"Pulling list of {count_objs_to_pull:,} objects from "
        f"{src_uri_root} for random sample..."
    )
    try:
        for (uri, size) in file_list_from_s3(GTFS_BUCKET, prefix):
            # Skip busloc TripUpdates because of S3 permission issues
            if size > 0 and skip_uri not in uri:
                uri_copy_set.add(uri)
            if len(uri_copy_set) == count_objs_to_pull:
                break
    except Exception as e:
        logging.error("Unable to pull file list from %s", src_uri_root)
        logging.exception(e)
        return 0

    s3_client = boto3.client("s3")
    success_count = 0
    print(
        f"Starting copy of {num_to_copy} random objects from {src_uri_root} ..."
    )
    for uri in random.sample(tuple(uri_copy_set), num_to_copy):
        key = str(uri).replace(f"s3://{GTFS_BUCKET}/", "")
        copy_source = {
            "Bucket": GTFS_BUCKET,
            "Key": key,
        }
        try:
            s3_client.copy(
                copy_source,
                DEV_INGEST_BUCKET,
                os.path.join(LAMP_PREFIX, key),
            )
        except Exception as e:
            logging.error("Copy failed for: %s", key)
            logging.exception(e)
        else:
            success_count += 1
    return success_count


def drill_s3_folders(
    client: boto3.client, bucket: str, prefix: str
) -> Iterable[str]:
    """
    Enumerate folders in specified bucket prefix combination
    """
    response = client.list_objects_v2(
        Bucket=bucket, Delimiter="/", Prefix=prefix, MaxKeys=45
    )
    if "CommonPrefixes" not in response:
        yield prefix
    else:
        for new_prefix in response["CommonPrefixes"]:
            yield from drill_s3_folders(client, bucket, new_prefix["Prefix"])


def copy_gfts_to_ingest(args: SetupArgs) -> None:
    """
    Enumerate folders in GTFS_BUCKET prefix and create workers to copy
    objects to development Ingest bucket
    """
    src_uri_root = f"s3://{os.path.join(GTFS_BUCKET, args.src_prefix)}"
    dest_urc_root = f"s3://{os.path.join(DEV_INGEST_BUCKET, LAMP_PREFIX)}"

    print(f"Enumerating folders in ({src_uri_root})...")
    s3_client = boto3.client("s3")
    folders = list(drill_s3_folders(s3_client, GTFS_BUCKET, args.src_prefix))
    # Get number of files to pull per folder
    per_folder = args.objs_to_copy // len(folders)
    # Number of folders that will have extra file
    remain = args.objs_to_copy % len(folders)
    print(
        f"{len(folders):,} folders found, "
        f"will copy ~{per_folder} objects from each folder."
    )

    # Combine list of folders and number of files to pull from each folder
    folder_pull_cnt = tuple(
        zip(
            folders,
            [
                per_folder + 1 if x < remain else per_folder
                for x in range(len(folders))
            ],
        )
    )

    action = None
    while action not in ("n", "no"):
        if action in ("y", "yes"):
            pool_size = os.cpu_count()
            if pool_size is None:
                pool_size = 4
            else:
                pool_size *= 2
            with Pool(pool_size) as pool:
                results = pool.starmap_async(copy_obj, folder_pull_cnt)
                success_count = 0
                for result in results.get():
                    success_count += result
            print(
                f"{success_count:,} objects copied, "
                f"{args.objs_to_copy - success_count} errors."
            )
            break

        print(
            f"Copy random selection of {args.objs_to_copy} objects "
            f"from {src_uri_root} to {dest_urc_root} ?\n"
            "yes(y) / no(n)"
        )
        action = input()


def main(args: SetupArgs) -> None:
    """
    Run functions to clear dev buckets and copy objects to ingest bucket.
    """
    clear_dev_buckets(args)
    copy_gfts_to_ingest(args)


if __name__ == "__main__":
    main(parse_args(sys.argv[1:]))
