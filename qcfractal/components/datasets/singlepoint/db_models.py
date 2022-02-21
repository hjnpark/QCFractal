from sqlalchemy import select, JSON, Column, Integer, ForeignKey, String, ForeignKeyConstraint, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import array_agg, JSONB
from sqlalchemy.orm import column_property, relationship
from sqlalchemy.orm.collections import attribute_mapped_collection

from qcfractal.components.datasets.db_models import CollectionORM, ContributedValuesORM
from qcfractal.components.records.singlepoint.db_models import QCSpecificationORM, SinglepointRecordORM
from qcfractal.db_socket import BaseORM


class SinglepointDatasetEntryORM(BaseORM):
    """Association table for many to many"""

    __tablename__ = "singlepoint_dataset_entries"

    dataset_id = Column(Integer, ForeignKey("singlepoint_dataset.id", ondelete="cascade"), primary_key=True)

    name = Column(String, nullable=False, primary_key=True)
    comment = Column(String)

    molecule_id = Column(Integer, ForeignKey("molecule.id"), nullable=False)
    additional_keywords = Column(JSONB, nullable=True)
    attributes = Column(JSONB, nullable=True)

    local_results = Column(JSON)


class SinglepointDatasetSpecificationORM(BaseORM):
    __tablename__ = "singlepoint_dataset_specifications"

    dataset_id = Column(Integer, ForeignKey("singlepoint_dataset.id", ondelete="cascade"), primary_key=True)
    name = Column(String, primary_key=True)
    description = Column(String, nullable=True)
    specification_id = Column(Integer, ForeignKey(QCSpecificationORM.id), nullable=False)

    specification = relationship(QCSpecificationORM, uselist=False)

    __table_args__ = (
        Index("ix_singlepoint_dataset_specifications_dataset_id", "dataset_id"),
        Index("ix_singlepoint_dataset_specifications_name", "name"),
        Index("ix_singlepoint_dataset_specifications_specification_id", "specification_id"),
    )


class SinglepointDatasetRecordItemORM(BaseORM):
    __tablename__ = "singlepoint_dataset_records"

    dataset_id = Column(Integer, ForeignKey("singlepoint_dataset.id", ondelete="cascade"), primary_key=True)
    entry_name = Column(String, primary_key=True)
    specification_name = Column(String, primary_key=True)
    record_id = Column(Integer, ForeignKey(SinglepointRecordORM.id), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["dataset_id", "entry_name"],
            ["singlepoint_dataset_entries.dataset_id", "singlepoint_dataset_entries.name"],
            ondelete="cascade",
            onupdate="cascade",
        ),
        ForeignKeyConstraint(
            ["dataset_id", "specification_name"],
            ["singlepoint_dataset_specifications.dataset_id", "singlepoint_dataset_specifications.name"],
            ondelete="cascade",
            onupdate="cascade",
        ),
        Index("ix_singlepoint_dataset_records_record_id", "record_id"),
        UniqueConstraint(
            "dataset_id", "entry_name", "specification_name", name="ux_singlepoint_dataset_records_unique"
        ),
    )


class SinglepointDatasetORM(CollectionORM):
    """
    The Dataset class for homogeneous computations on many molecules.
    """

    __tablename__ = "singlepoint_dataset"

    id = Column(Integer, ForeignKey(CollectionORM.id, ondelete="cascade"), primary_key=True)

    contributed_values = relationship(ContributedValuesORM, lazy="selectin", cascade="all, delete-orphan")

    specifications = relationship(
        SinglepointDatasetSpecificationORM, collection_class=attribute_mapped_collection("name")
    )

    entries = relationship(SinglepointDatasetEntryORM, collection_class=attribute_mapped_collection("name"))

    record_items = relationship(SinglepointDatasetRecordItemORM)

    entry_names = column_property(
        select(array_agg(SinglepointDatasetEntryORM.name))
        .where(SinglepointDatasetEntryORM.dataset_id == id)
        .scalar_subquery()
    )

    __mapper_args__ = {
        "polymorphic_identity": "singlepoint",
    }
