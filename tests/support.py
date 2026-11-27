from contextlib import contextmanager

from clinic_dq.config import Config
from clinic_dq.loader import LoadedDataset, load_dataset


@contextmanager
def open_dataset(
    config: Config,
    dataset: str = "clean",
    mutations: set[str] | None = None,
):
    loaded: LoadedDataset = load_dataset(config, dataset=dataset, mutations=mutations)
    try:
        yield loaded
    finally:
        loaded.connection.close()
