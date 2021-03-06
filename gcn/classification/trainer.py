import pandas as pd
from tensorflow.python import keras as K
from chariot.preprocess import Preprocess
from chariot.feeder import Feeder
from chariot.transformer.formatter import Padding
from gcn.base_trainer import BaseTrainer
from gcn.data.multi_nli_dataset import MultiNLIDataset
from gcn.graph.dependency_graph import DependencyGraph
from gcn.graph.similarity_graph import SimilarityGraph
from gcn.graph.static_graph import StaticGraph


class Trainer(BaseTrainer):

    def __init__(self, graph_builder, root="", min_df=1, max_df=1.0,
                 unknown="<unk>", preprocessor_name="preprocessor",
                 log_dir=""):
        super().__init__(root, graph_builder.lang, min_df, max_df, unknown,
                         preprocessor_name, log_dir)
        self.graph_builder = graph_builder

    def download(self):
        r = MultiNLIDataset(self.storage.root).download()
        return r

    @property
    def num_classes(self):
        return len(MultiNLIDataset.labels())

    def build(self, data_kind="train", save=True):
        super().build(data_kind, "text", save)
        if self.preprocessor.vocabulary.pad != 0:
            raise Exception("Padding is not executed by zero.")

    def train(self, model, data_kind="train",
              lr=1e-3, batch_size=20, sequence_length=25,
              representation="GloVe.6B.100d",
              epochs=40, verbose=2):

        if not self._built:
            raise Exception("Trainer's preprocessor is not built.")

        if representation is not None:
            self.storage.chakin(name=representation)
            file_path = "external/{}.txt".format(representation.lower())
            weights = [self.preprocessor.vocabulary.make_embedding(
                                self.storage.data_path(file_path))]
            model.get_layer("embedding").set_weights(weights)

        r = self.download()

        train_data = self.preprocess(r.train_data(), sequence_length)
        test_data = self.preprocess(r.test_data(), sequence_length)

        # Set optimizer
        model.compile(loss="sparse_categorical_crossentropy",
                      optimizer=K.optimizers.Adam(lr=lr),
                      metrics=["accuracy"])

        validation_data = ((test_data["text"], test_data["graph"]), test_data["label"])
        metrics = model.fit((train_data["text"], train_data["graph"]),
                            train_data["label"],
                            validation_data=validation_data,
                            batch_size=batch_size,
                            epochs=epochs, verbose=verbose)

        return metrics

    def preprocess(self, data, length):
        _data = data
        if isinstance(data, (list, tuple)):
            _data = pd.Series(data, name="text").to_frame()
        elif isinstance(data, pd.Series):
            _data = data.to_frame()

        graph = self.graph_builder.batch_build(_data["text"], length)

        preprocess = Preprocess({
            "text": self.preprocessor
        })
        feeder = Feeder({"text": Padding.from_(self.preprocessor,
                                               length=length)})

        _data = preprocess.transform(_data)
        _data = feeder.transform(_data)
        _data["graph"] = graph

        return _data
