import argparse
import datetime
import os
import requests
import logging
import shutil
import subprocess

from pathlib import Path

import git

logger = logging.getLogger(__name__)


def is_recent_people_repo_commit() -> bool:
    repo_url = "https://api.github.com/repos/openstates/people/commits"
    response = requests.get(repo_url)
    no_new_commit = False
    if response.status_code == 200:
        latest_commit = response.json()[0]
        last_commit_time = latest_commit["commit"]["committer"]["date"]
        # Ensure it's UTC-aware
        last_commit_time = datetime.datetime.fromisoformat(
            last_commit_time.rstrip("Z")
        ).replace(tzinfo=datetime.timezone.utc)
        two_hours_ago = datetime.datetime.now(
            datetime.timezone.utc
        ) - datetime.timedelta(
            minutes=2 * 60 + 5
        )  # 2 hours and 5-minute buffer.
        no_new_commit = last_commit_time > two_hours_ago
    return no_new_commit


def clone_people_repo() -> None:
    repo_name = "people"
    data_path = "data"
    base_dir = (
        Path(os.environ["OS_PEOPLE_DIRECTORY"])
        if "OS_PEOPLE_DIRECTORY" in os.environ
        else Path(".")
    )
    if (base_dir / data_path).is_dir():
        logger.info(f"{repo_name} directory exist")
        return
    logger.info(f"Cloning {repo_name}")
    git.refresh("/usr/bin/git")
    repo_url_ssh = "git@github.com:openstates/people.git"
    git.Repo.clone_from(repo_url_ssh, repo_name)
    logger.info(f"Done cloning {repo_name}!")

    current_directory = base_dir / repo_name
    source_data_dir = current_directory / data_path
    destination_data_dir = base_dir / data_path
    shutil.copytree(source_data_dir, destination_data_dir)


def opts():
    parser = argparse.ArgumentParser(
        description="Trigger Openstates people and committees to-database",
    )
    parser.add_argument(
        "--force-ingest",
        "-f",
        action="store_true",
        help="Optionally set to True to force ingestion regardless of last commit",
    )
    parser.add_argument(
        "--purge",
        "-p",
        action="store_true",
        help="Set to True to purge old data from database",
    )
    parser.add_argument(
        "--data-class",
        "-d",
        type=str,
        help="Set to True to purge old data from database",
    )
    return parser.parse_args()


def main():
    args = opts()
    is_purge = args.purge
    data_class = args.data_class
    if not args.force_ingest:
        logger.info("Checking if an update is necessary")
        if not is_recent_people_repo_commit():
            logger.info(
                "There was no recent update to Openstates People Repo \n exiting..."
            )
            return 0

    logger.info(
        "An update is necessary...\nBegin updating Openstates People to-database!"
    )
    clone_people_repo()
    people_arguments = ["python", "-m", "openstates.cli.people", "to-database"]
    committee_arguments = ["python", "-m", "openstates.cli.committees", "to-database"]
    if is_purge:
        people_arguments.append("--purge")
        committee_arguments.append("--purge")
    if data_class == "people":
        subprocess.run(people_arguments)
    elif data_class == "committees":
        subprocess.run(committee_arguments)
    else:
        subprocess.run(people_arguments)
        subprocess.run(committee_arguments)


if __name__ == "__main__":
    main()
