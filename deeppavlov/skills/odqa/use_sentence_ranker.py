from typing import List, Tuple, Any
import time

import numpy as np
import tensorflow_hub as hub
import tensorflow as tf

from deeppavlov.core.common.registry import register
from deeppavlov.core.models.component import Component
from deeppavlov.core.commands.utils import expand_path


@register('use_sentence_ranker')
class USESentenceRanker(Component):
    def __init__(self, top_n=20, return_vectors=False, active: bool = True, **kwargs):
        """
        :param top_n: top n sentences to return
        :param return_vectors: return unranged USE vectors instead of sentences
        :param active: when is not active, return all sentences
        """
        self.embed = hub.Module(str(expand_path("enog/hub")))
        self.session = tf.Session(config=tf.ConfigProto(
            gpu_options=tf.GPUOptions(
                per_process_gpu_memory_fraction=0.4,
                allow_growth=False
            )))
        self.session.run([tf.global_variables_initializer(), tf.tables_initializer()])
        self.q_ph = tf.placeholder(shape=(None,), dtype=tf.string)
        self.c_ph = tf.placeholder(shape=(None,), dtype=tf.string)
        self.q_emb = self.embed(self.q_ph)
        self.c_emb = self.embed(self.c_ph)
        self.top_n = top_n
        self.return_vectors = return_vectors
        self.active = active

    def __call__(self, query_context: List[Tuple[str, List[str]]]):
        """
        Rank sentences and return top n sentences.
        """
        predictions = []
        all_top_scores = []
        fake_scores = [0.001] * len(query_context)

        for el in query_context:
            # DEBUG
            # start_time = time.time()
            qe, ce = self.session.run([self.q_emb, self.c_emb],
                                      feed_dict={
                                          self.q_ph: [el[0]],
                                          self.c_ph: el[1],
                                      })
            # print("Time spent: {}".format(time.time() - start_time))
            if self.return_vectors:
                predictions.append((qe, ce))
            else:
                scores = (qe @ ce.T).squeeze()
                if self.active:
                    thresh = self.top_n
                else:
                    thresh = len(el[1])
                if scores.size == 1:
                    scores = [scores]
                top_scores = np.sort(scores)[::-1][:thresh]
                all_top_scores.append(top_scores)
                # Sorts the sentences!
                # sentence_top_ids = np.argsort(scores)[::-1][:thresh]
                # predictions.append([el[1][x] for x in sentence_top_ids])
                predictions.append(el[1])
        if self.return_vectors:
            return predictions, fake_scores
        else:
            return [' '.join(sentences) for sentences in predictions], all_top_scores
