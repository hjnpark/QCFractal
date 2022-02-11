from typing import Union

from .models import BaseDataset, DatasetQueryModel, DatasetGetEntryBody, DatasetGetRecordItemsBody

# All possible datasets we can get from the server
from .optimization.models import OptimizationDataset

AllDatasetTypes = Union[OptimizationDataset]
AllDatasetDataModelTypes = Union[OptimizationDataset._DataModel]
