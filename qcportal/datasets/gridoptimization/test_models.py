from __future__ import annotations

from typing import TYPE_CHECKING

import qcportal.datasets.testing_helpers as ds_helpers
from qcportal.datasets.gridoptimization import GridoptimizationDatasetNewEntry
from qcportal.molecules import Molecule
from qcportal.records import PriorityEnum
from qcportal.records.gridoptimization import GridoptimizationKeywords
from qcportal.records.optimization.models import OptimizationSpecification, OptimizationProtocols
from qcportal.records.singlepoint.models import QCSpecification

if TYPE_CHECKING:
    from qcportal import PortalClient

test_entries = [
    GridoptimizationDatasetNewEntry(
        name="hydrogen_4",
        initial_molecule=Molecule(symbols=["h", "h", "h", "h"], geometry=[0, 0, 0, 0, 0, 2, 0, 0, 4, 0, 0, 6]),
        gridoptimization_keywords=GridoptimizationKeywords(
            preoptimization=False,
            scans=[
                {"type": "distance", "indices": [1, 2], "steps": [-0.1, 0.0], "step_type": "relative"},
                {"type": "dihedral", "indices": [0, 1, 2, 3], "steps": [-90, 0], "step_type": "absolute"},
            ],
        ),
    ),
    GridoptimizationDatasetNewEntry(
        name="h_4_2",
        initial_molecule=Molecule(symbols=["h", "h", "h", "h"], geometry=[0, 0, 0, 0, 0, 3, 0, 0, 6, 0, 0, 9]),
        gridoptimization_keywords=GridoptimizationKeywords(
            preoptimization=False,
            scans=[
                {"type": "distance", "indices": [1, 2], "steps": [-0.2, 0.1], "step_type": "relative"},
                {"type": "dihedral", "indices": [0, 1, 2, 3], "steps": [-45, 0], "step_type": "absolute"},
            ],
        ),
        attributes={"internal": "internal_id"},
    ),
    GridoptimizationDatasetNewEntry(
        name="ne_4",
        initial_molecule=Molecule(symbols=["ne", "ne", "ne", "ne"], geometry=[0, 0, 0, 0, 0, 2, 0, 0, 4, 0, 0, 6]),
        gridoptimization_keywords=GridoptimizationKeywords(
            preoptimization=True,
            scans=[
                {"type": "distance", "indices": [3, 4], "steps": [-0.2, 0.1], "step_type": "relative"},
                {"type": "dihedral", "indices": [2, 3, 1, 4], "steps": [-15, 0], "step_type": "absolute"},
            ],
        ),
        additional_keywords={"maxiter": 1234},
    ),
]

test_specs = [
    OptimizationSpecification(
        program="opt_prog_1",
        qc_specification=QCSpecification(
            program="prog1", driver="deferred", method="b3lyp", basis="6-31g*", keywords={"maxiter": 20}
        ),
        keywords={"opt_kw_1": 123, "opt_kw_2": "a string"},
    ),
    OptimizationSpecification(
        program="opt_prog_2",
        qc_specification=QCSpecification(
            program="prog2", driver="deferred", method="hf", basis="sto-3g", keywords={"maxiter": 40}
        ),
        keywords={"opt_kw_1": 456, "opt_kw_2": "another string"},
        protocols=OptimizationProtocols(trajectory="none"),
    ),
    OptimizationSpecification(
        program="opt_prog_3",
        qc_specification=QCSpecification(
            program="prog3", driver="deferred", method="hf", basis="sto-3g", keywords={"maxiter": 40}
        ),
        keywords={"opt_kw_1": 789, "opt_kw_2": "another string 2"},
        protocols=OptimizationProtocols(trajectory="final"),
    ),
]


def entry_extra_compare(ent1, ent2):
    assert ent1.initial_molecule == ent2.initial_molecule


def record_compare(rec, ent, spec):
    assert ent.initial_molecule == rec.initial_molecule
    assert rec.specification.optimization_specification == spec
    assert rec.specification.keywords == ent.gridoptimization_keywords


def test_gridoptimization_dataset_model_add_get_entry(snowflake_client: PortalClient):
    ds = snowflake_client.add_dataset("gridoptimization", "Test dataset")
    ds_helpers.run_dataset_model_add_get_entry(snowflake_client, ds, test_entries, entry_extra_compare)


def test_gridoptimization_dataset_model_add_entry_duplicate(snowflake_client: PortalClient):
    ds = snowflake_client.add_dataset("gridoptimization", "Test dataset")
    ds_helpers.run_dataset_model_add_entry_duplicate(snowflake_client, ds, test_entries, entry_extra_compare)


def test_gridoptimization_dataset_model_delete_entry(snowflake_client: PortalClient):
    ds = snowflake_client.add_dataset("gridoptimization", "Test dataset")
    ds_helpers.run_dataset_model_delete_entry(snowflake_client, ds, test_entries, test_specs)


def test_gridoptimization_dataset_model_add_get_spec(snowflake_client: PortalClient):
    ds = snowflake_client.add_dataset("gridoptimization", "Test dataset")
    ds_helpers.run_dataset_model_add_get_spec(snowflake_client, ds, test_specs)


def test_gridoptimization_dataset_model_add_spec_duplicate(snowflake_client: PortalClient):
    ds = snowflake_client.add_dataset("gridoptimization", "Test dataset")
    ds_helpers.run_dataset_model_add_spec_duplicate(snowflake_client, ds, test_specs)


def test_gridoptimization_dataset_model_delete_spec(snowflake_client: PortalClient):
    ds = snowflake_client.add_dataset("gridoptimization", "Test dataset")
    ds_helpers.run_dataset_model_delete_spec(snowflake_client, ds, test_entries, test_specs)


def test_gridoptimization_dataset_model_remove_record(snowflake_client: PortalClient):
    ds = snowflake_client.add_dataset("gridoptimization", "Test dataset")
    ds_helpers.run_dataset_model_remove_record(snowflake_client, ds, test_entries, test_specs)


def test_gridoptimization_dataset_model_submit(snowflake_client: PortalClient):
    ds = snowflake_client.add_dataset(
        "gridoptimization", "Test dataset", default_tag="default_tag", default_priority=PriorityEnum.low
    )
    ds_helpers.run_dataset_model_submit(ds, test_entries, test_specs[0], record_compare)


def test_gridoptimization_dataset_model_submit_missing(snowflake_client: PortalClient):
    ds = snowflake_client.add_dataset("gridoptimization", "Test dataset")
    ds_helpers.run_dataset_model_submit_missing(ds)


def test_gridoptimization_dataset_model_iterate_updated(snowflake_client: PortalClient):
    ds = snowflake_client.add_dataset("gridoptimization", "Test dataset")
    ds_helpers.run_dataset_model_iterate_updated(ds, test_entries, test_specs[0])


def test_gridoptimization_dataset_model_modify_records(snowflake_client: PortalClient):
    ds = snowflake_client.add_dataset("gridoptimization", "Test dataset")
    ds_helpers.run_dataset_model_modify_records(ds, test_entries, test_specs[0])