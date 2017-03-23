#!/bin/python3

from collections import defaultdict
import abc
import bz2
import argparse
import csv
import os.path
import requests
import sqlite3
import sys
import tempfile
import time
import xml.etree.ElementTree
from sqlalchemy import (create_engine, Column, String)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

Base = declarative_base()

DEFAULT_DISTRO = "rh-dist-git"
SNAPSHOT = "reverse-dist-git.latest.tsv"
SNAPSHOT_REMOTE_DIR_URL = "http://file.bos.redhat.com/~ahills/dist-git/"
SNAPSHOT_URL = SNAPSHOT_REMOTE_DIR_URL + SNAPSHOT
SNAPSHOT_LOCAL_DIR = tempfile.gettempdir()
SNAPSHOT_PATH = os.path.join(SNAPSHOT_LOCAL_DIR, SNAPSHOT)

SCL_PACKAGE_LISTS_URL =\
    "http://git.app.eng.bos.redhat.com/git/RH_Software_Collections.git/plain/PackageLists/"
SCL_PACKAGE_LISTS = {
    "nodejs010": SCL_PACKAGE_LISTS_URL + "nodejs010/all",
    "rh-nodejs4": SCL_PACKAGE_LISTS_URL + "rh-nodejs4/all",
    "python27": SCL_PACKAGE_LISTS_URL + "python27/all",
    "python33": SCL_PACKAGE_LISTS_URL + "python33/all",
    "rh-python34": SCL_PACKAGE_LISTS_URL + "rh-python34/all",
    "rh-python35": SCL_PACKAGE_LISTS_URL + "rh-python35/all"
}

REPOMD_URL = "http://download-node-02.eng.bos.redhat.com/rel-eng/RHEL-7.3-RC-3.0/compose/Server/x86_64/os/repodata/repomd.xml"
REPODATA_LOCAL_DIR = tempfile.gettempdir()
REPOMD_PATH = os.path.join(REPODATA_LOCAL_DIR, 'repomd.xml')
REPODATA_PRIMARY_DB_PATH = os.path.join(REPODATA_LOCAL_DIR, "primary.sqlite")


class DownstreamMap(Base):
    __tablename__ = 'downstream_map'
    key = Column(String(255), primary_key=True)
    value = Column(String(512), nullable=False)


class DownstreamMapCache(object):
    def __init__(self):
        super().__init__()
        self.connection_string = 'postgres://{POSTGRESQL_USER}:{POSTGRESQL_PASSWORD}@{PGBOUNCER_SERVICE_HOST}:5432/{POSTGRESQL_DATABASE}?sslmode=disable'.format(**os.environ)
        self.session = None

    def is_connected(self):
        return self.session is not None

    def connect(self):
        if self.is_connected():
            return

        pong = False
        while not pong:
            try:
                engine = create_engine(self.connection_string,
                                       poolclass=NullPool)
                self.session = sessionmaker(bind=engine)()
                # Base.metadata.create_all(engine)  # Let Alembic do that
            except OperationalError:
                print("Can't connect to DB - sleeping")
                time.sleep(1)
            else:
                pong = True

        pong = False
        while not pong:
            try:
                self.session.query(DownstreamMap).count()
            except ProgrammingError:
                self.session.rollback()
                print("Waiting for Alembic to create table")
                time.sleep(1)
            else:
                pong = True

    def disconnect(self):
        if self.is_connected():
            self.session.close()
            self.session = None

    def get(self, key):
        """ Returns None if key is not in DB """
        return self.session.query(DownstreamMap) \
                           .filter(DownstreamMap.key == key) \
                           .first()

    def delete_all(self):
        print("Cleaning DB")
        try:
            self.session.query(DownstreamMap).delete()
            self.session.commit()
        except:
            self.session.rollback()
            raise

    def update_mappings(self, mappings):
        print("Updating DB")
        try:
            self.session.bulk_update_mappings(DownstreamMap, mappings)
            self.session.commit()
        except:
            self.session.rollback()
            raise

    def insert_mappings(self, mappings):
        print("Inserting into DB")
        try:
            self.session.bulk_insert_mappings(DownstreamMap, mappings)
            self.session.commit()
        except:
            self.session.rollback()
            raise


class Import(metaclass=abc.ABCMeta):
    def __init__(self):
        self.prefixes_map = defaultdict(set)
        self.cache = None

    def connect(self):
        print("Connecting to DB")
        self.cache = DownstreamMapCache()
        self.cache.connect()

    def disconnect(self):
        self.cache.disconnect()
        self.cache = None

    @staticmethod
    @abc.abstractmethod
    def download():
        pass

    @abc.abstractmethod
    def download_and_import(self, download_only=False):
        pass


class ReverseDistGit(Import):
    @staticmethod
    def download():
        # Download dist-git snapshot. Rewrites older one if already exists.
        print("Downloading dist-git snapshot from {}".format(SNAPSHOT_URL))
        try:
            downloaded_snapshot = requests.get(SNAPSHOT_URL)
        except requests.exceptions.RequestException as e:
            print("Failed to download dist-git snapshot. Reason: ", e)
            return 1

        if not downloaded_snapshot.ok:
            print("Failed to download dist-git snapshot. Reason: ", downloaded_snapshot.reason)
            return 1

        try:
            with open(SNAPSHOT_PATH, "wb") as dg_snapshot:
                dg_snapshot.write(downloaded_snapshot.content)
        except OSError as e:
            print("Failed to write dist-git snapshot. Reason: ", e)
            return 1

        return 0

    def map_package_to_prefixes(self):
        # Create map of package -> prefixes
        try:
            for prefix in SCL_PACKAGE_LISTS:
                try:
                    downloaded_package_list = requests.get(SCL_PACKAGE_LISTS[prefix])
                except requests.exceptions.RequestException as e:
                    print("Failed to download package list from %s. Reason: %s" %
                          (SCL_PACKAGE_LISTS[prefix], e))
                    continue
                if downloaded_package_list.ok:
                    for package_with_prefix in downloaded_package_list.text.splitlines():
                        package_with_prefix = package_with_prefix.split()[0]
                        base_package = package_with_prefix[len(prefix) + 1:]
                        if base_package:
                            self.prefixes_map[base_package].add(package_with_prefix)
                else:
                    print("Failed to download package list from %s. Reason: %s" %
                          (SCL_PACKAGE_LISTS[prefix], downloaded_package_list.reason))
        except Exception as e:
            print("Creating prefixes_map failed:", e)
            # Not necessary, do not let it ruin the rest of the script
            pass

    def load_into_cache(self):
        """ Load the latest dist-git snapshot into cache if needed """
        snapshot_tsv = csv.reader(open(SNAPSHOT_PATH, newline=""), delimiter="\t")
        mappings = {}
        for artifact_hash, fname, package in snapshot_tsv:
            if package in self.prefixes_map:
                package += "," + ",".join(self.prefixes_map[package])
            cache_entry = "{} {} {}".format(DEFAULT_DISTRO, fname, package)
            mappings[artifact_hash] = cache_entry
        mappings = [{'key': k, 'value': v} for k, v in mappings.items()]
        # Delete all rows, then bulk insert new records with session.bulk_insert_mappings()
        # This is the fastest way how to insert 200K records I've been able to find. I tried:
        # - only session.bulk_insert_mappings() - fails if any of inserted keys already exists
        # - session.bulk_update_mappings() - fails if any of updated keys does not exist
        # - query DB for keys and bulk_insert_mappings() only not existing - takes eternity
        self.cache.delete_all()
        self.cache.insert_mappings(mappings)
        print("Uploaded {} dist-git cache entries".format(len(mappings)))

    def download_and_import(self, download_only=False):
        status = self.download()
        if download_only:
            # image build
            return status
        if not os.path.exists(SNAPSHOT_PATH):
            # container start up
            print("No dist-git snapshot available")
            return 1
        self.map_package_to_prefixes()
        try:
            self.connect()
        except Exception as e:
            print("Unexpected error while connecting to DB: %s" % str(e))
            sys.exit(1)
        self.load_into_cache()
        self.disconnect()
        return 0


class SRPMProvide(Import):
    @staticmethod
    def download():
        print("Downloading repomd.xml from {}".format(REPOMD_URL))
        try:
            downloaded_repomd = requests.get(REPOMD_URL)
        except requests.exceptions.RequestException as e:
            print("Failed to download repomd.xml file. Reason: ", e)
            return 1

        if not downloaded_repomd.ok:
            print("Failed to download repomd.xml. Reason: ", downloaded_repomd.reason)
            return 1

        print("Parsing repomd.xml to get primary DB URL")
        tree = xml.etree.ElementTree.fromstring(downloaded_repomd.content)
        namespace = tree.tag.split('}')[0] + '}'
        primary_db_location_xpath = \
            "./{ns}data[@type='primary_db']/{ns}location".format(ns=namespace)
        primary_db_location = tree.find(primary_db_location_xpath)
        if primary_db_location is None:
            print("Failed to find a match for {} in repodata".format(primary_db_location_xpath))
            return 1
        location = primary_db_location.get("href")
        primary_db_url = REPOMD_URL[:-(len("repomd.xml"))] + location[len("repodata/"):]

        print("Downloading and extracting primary DB from {}".format(primary_db_url))
        try:
            downloaded_db = requests.get(primary_db_url)
        except requests.exceptions.RequestException as e:
            print("Failed to download primary DB file. Reason: ", e)
            return 1

        if downloaded_db.ok:
            with open(REPODATA_PRIMARY_DB_PATH, "wb") as primary_db:
                primary_db.write(bz2.decompress(downloaded_db.content))
        else:
            print("Failed to download primary DB file. Reason: ", downloaded_db.reason)
            return 1

        return 0

    def get_mapping(self):
        mapping = defaultdict(set)
        db = sqlite3.connect(REPODATA_PRIMARY_DB_PATH)
        result = db.execute("SELECT provides.name AS provname, packages.name AS pkgname " +
                            "FROM provides JOIN packages ON provides.pkgKey = packages.pkgKey " +
                            "WHERE provides.name LIKE \"mvn(%)\"")
        for row in result:
            group_artifact = row[0][4:-1]
            rpm_name = row[1]
            mapping[group_artifact].add(rpm_name)
        return mapping

    def load_into_cache(self, mapping):
        mappings = [{'key': k, 'value': "{} {}".format(DEFAULT_DISTRO, ",".join(v))}
                    for k, v in mapping.items()]
        self.cache.insert_mappings(mappings)
        print("Uploaded {} maven entries".format(len(mappings)))

    def download_and_import(self, download_only=False):
        status = self.download()
        if download_only:
            # image build
            return status
        if not os.path.exists(REPODATA_PRIMARY_DB_PATH):
            # container start up
            print("No repodata available")
            return 1
        mapping = self.get_mapping()
        try:
            self.connect()
        except Exception as e:
            print("Unexpected error while connecting to DB: %s" % str(e))
            sys.exit(1)
        self.load_into_cache(mapping)
        self.disconnect()
        return 0


class CLI(object):
    def __init__(self):
        self.parser = argparse.ArgumentParser(formatter_class=argparse.HelpFormatter)
        self.parser.add_argument("--download-only", action="store_true",
                                 help='only download dist-git snapshot')

    def run(self):
        args = self.parser.parse_args()
        rrdgi = ReverseDistGit()
        rspi = SRPMProvide()
        reverse_res = rrdgi.download_and_import(args.download_only)
        srpm_res = rspi.download_and_import(args.download_only)
        return reverse_res or srpm_res

if __name__ == '__main__':
    cli = CLI()
    sys.exit(cli.run())
