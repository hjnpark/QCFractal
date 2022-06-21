"""
Contains testing infrastructure for QCFractal.
"""
from __future__ import annotations

import json
import lzma
import os
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Dict, List, Union, Tuple, Optional

import pydantic
from qcelemental.models import Molecule, FailedOperation, OptimizationResult, AtomicResult
from qcelemental.models.results import WavefunctionProperties

from qcportal.records import PriorityEnum
from qcportal.records.gridoptimization import GridoptimizationSpecification
from qcportal.records.manybody import ManybodySpecification
from qcportal.records.optimization import OptimizationSpecification
from qcportal.records.reaction import ReactionSpecification
from qcportal.records.singlepoint import QCSpecification
from qcportal.records.torsiondrive import TorsiondriveSpecification
from qcportal.records.neb import NEBSpecification
from qcportal.serialization import _json_decode

if TYPE_CHECKING:
    from qcfractal.db_socket import SQLAlchemySocket

# Valid client encodings
valid_encodings = ["application/json", "application/msgpack"]

# Path to this file (directory only)
_my_path = os.path.dirname(os.path.abspath(__file__))

geoip_path = os.path.join(_my_path, "MaxMind-DB", "test-data", "GeoIP2-City-Test.mmdb")

test_users = {
    "admin_user": {
        "pw": "something123",
        "info": {
            "role": "admin",
            "fullname": "Mrs. Admin User",
            "organization": "QCF Testing",
            "email": "admin@example.com",
        },
    },
    "read_user": {
        "pw": "something123",
        "info": {
            "role": "read",
            "fullname": "Mr. Read User",
            "organization": "QCF Testing",
            "email": "read@example.com",
        },
    },
    "monitor_user": {
        "pw": "something123",
        "info": {
            "role": "monitor",
            "fullname": "Mr. Monitor User",
            "organization": "QCF Testing",
            "email": "monitor@example.com",
        },
    },
    "compute_user": {
        "pw": "something123",
        "info": {
            "role": "compute",
            "fullname": "Mr. Compute User",
            "organization": "QCF Testing",
            "email": "compute@example.com",
        },
    },
    "submit_user": {
        "pw": "something123",
        "info": {
            "role": "submit",
            "fullname": "Mrs. Submit User",
            "organization": "QCF Testing",
            "email": "submit@example.com",
        },
    },
}


def read_record_data(name: str):
    """
    Loads pre-computed/dummy procedure data from the test directory

    Parameters
    ----------
    name
        The name of the file to load (without the json extension)

    Returns
    -------
    :
        A dictionary with all the data in the file

    """

    data_path = os.path.join(_my_path, "procedure_data")
    file_path = os.path.join(data_path, name + ".json.xz")
    is_xz = True

    if not os.path.exists(file_path):
        file_path = os.path.join(data_path, name + ".json")
        is_xz = False

    if not os.path.exists(file_path):
        raise RuntimeError(f"Procedure data file {file_path} not found!")

    if is_xz:
        with lzma.open(file_path, "rt") as f:
            data = json.load(f, object_hook=_json_decode)
    else:
        with open(file_path, "r") as f:
            data = json.load(f, object_hook=_json_decode)

    return data


def load_molecule_data(name: str) -> Molecule:
    """
    Loads a molecule object for use in testing
    """

    data_path = os.path.join(_my_path, "molecule_data")
    file_path = os.path.join(data_path, name + ".json")
    return Molecule.from_file(file_path)


def load_wavefunction_data(name: str) -> WavefunctionProperties:
    """
    Loads a wavefunction object for use in testing
    """

    data_path = os.path.join(_my_path, "wavefunction_data")
    file_path = os.path.join(data_path, name + ".json")

    with open(file_path, "r") as f:
        data = json.load(f)
    return WavefunctionProperties(**data)


def load_ip_test_data():
    """
    Loads data for testing IP logging
    """

    file_path = os.path.join(_my_path, "MaxMind-DB", "source-data", "GeoIP2-City-Test.json")

    with open(file_path, "r") as f:
        d = json.load(f)

    # Stored as a list containing a dictionary with one key. Convert to a regular dict
    ret = {}
    for x in d:
        ret.update(x)

    return ret


@contextmanager
def caplog_handler_at_level(caplog_fixture, level, logger=None):
    """
    Helper function to set the caplog fixture's handler to a certain level as well, otherwise it wont be captured

    e.g. if caplog.set_level(logging.INFO) but caplog.handler is at logging.CRITICAL, anything below CRITICAL wont be
    captured.
    """
    starting_handler_level = caplog_fixture.handler.level
    caplog_fixture.handler.setLevel(level)
    with caplog_fixture.at_level(level, logger=logger):
        yield
    caplog_fixture.handler.setLevel(starting_handler_level)


def terminate_process(proc):
    if proc.poll() is None:

        # Interrupt (SIGINT)
        if sys.platform.startswith("win"):
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.send_signal(signal.SIGINT)

        try:
            start = time.time()
            while (proc.poll() is None) and (time.time() < (start + 15)):
                time.sleep(0.02)

        # Kill (SIGKILL)
        finally:
            proc.kill()


@contextmanager
def popen(args):
    """
    Opens a background task.
    """
    args = list(args)

    # Bin prefix
    if sys.platform.startswith("win"):
        bin_prefix = os.path.join(sys.prefix, "Scripts")
    else:
        bin_prefix = os.path.join(sys.prefix, "bin")

    # First argument is the executable name
    # We are testing executable scripts found in the bin directory
    args[0] = os.path.join(bin_prefix, args[0])

    # Add coverage testing
    coverage_dir = os.path.join(bin_prefix, "coverage")
    if not os.path.exists(coverage_dir):
        print("Could not find Python coverage, skipping cov.")
    else:
        src_dir = os.path.dirname(os.path.abspath(__file__))
        # --source is the path to the QCFractal source
        # --parallel-mode means every process gets its own file (useful because we do multiple processes)
        coverage_flags = [coverage_dir, "run", "--parallel-mode", "--source=" + src_dir]
        args = coverage_flags + args

    kwargs = {}
    if sys.platform.startswith("win"):
        # Allow using CTRL_C_EVENT / CTRL_BREAK_EVENT
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    kwargs["stdout"] = subprocess.PIPE
    kwargs["stderr"] = subprocess.PIPE
    proc = subprocess.Popen(args, **kwargs)
    try:
        yield proc
    except Exception:
        raise
    finally:
        try:
            terminate_process(proc)
        finally:
            output, error = proc.communicate()
            print("-" * 80)
            print("|| Process command: {}".format(" ".join(args)))
            print("|| Process stdout: \n{}".format(output.decode()))
            print("-" * 80)
            print()
            if error:
                print("\n|| Process stderr: \n{}".format(error.decode()))
                print("-" * 80)


def run_process(args, interrupt_after=15):
    """
    Runs a process in the background until complete.

    Returns True if exit code zero.
    """

    with popen(args) as proc:
        try:
            proc.wait(timeout=interrupt_after)
        except subprocess.TimeoutExpired:
            pass
        finally:
            terminate_process(proc)

        retcode = proc.poll()

    return retcode == 0
