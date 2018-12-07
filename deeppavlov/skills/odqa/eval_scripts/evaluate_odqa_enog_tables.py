"""
Count a ranker recall.
Need:
1. A ranker config (with rank, text, score, text_id API) for a specific domain (eg. "en_drones")
2. QA dataset for this domain.
"""

import argparse
import time
import unicodedata
import logging
import csv

import numpy as np

from deeppavlov.core.common.file import read_json
from deeppavlov.core.commands.infer import build_model_from_config
from deeppavlov.metrics.squad_metrics import squad_f1, exact_match

logger = logging.getLogger()
logger.setLevel(logging.INFO)
fmt = logging.Formatter('%(asctime)s: [ %(message)s ]', '%m/%d/%Y %I:%M:%S %p')
file = logging.FileHandler('../eval_logs/ranker_ensemble_enog_tables.log')
file.setFormatter(fmt)
logger.addHandler(file)

parser = argparse.ArgumentParser()

parser.add_argument("-config_path", help="path to a JSON ranker config", type=str,
                    default='../../../../deeppavlov/configs/odqa/enog/enog_odqa_tables.json')
parser.add_argument("-dataset_path", help="path to a QA TSV dataset", type=str,
                    default='/media/olga/Data/datasets/enog/tables/questions_v3_answers.tsv')
parser.add_argument("-output_path", help="path to a QA TSV dataset", type=str,
                    default='/media/olga/Data/datasets/enog/tables/tables_predictions_v3.csv')


def normalize(s: str):
    return unicodedata.normalize('NFD', s)


def instance_score_by_text(answers, texts):
    formatted_answers = [normalize(a.strip().lower()) for a in answers]
    formatted_texts = [normalize(text.lower()) for text in texts]
    for a in formatted_answers:
        for doc_text in formatted_texts:
            if doc_text.find(a) != -1:
                return 1
    return 0

# def instance_score_by_table_id(answers, texts):
#     formatted_answers = [normalize(a.strip().lower()) for a in answers]
#     formatted_texts = [normalize(text.lower()) for text in texts]
#     for a in formatted_answers:
#         for doc_text in formatted_texts:
#             if doc_text.find(a) != -1:
#                 return 1
#     return 0


def read_tsv(tsv_path):
    # convert file to utf-8
    output = []
    with open(tsv_path) as fin:
        reader = csv.reader(fin)
        for item in reader:
            try:
                output.append({'table_id': item[0],
                               'question': item[1],
                               'answer': item[2]})
            except Exception:
                logger.info("Exception in read_tsv()")
    return output


def main():
    args = parser.parse_args()
    config = read_json(args.config_path)
    odqa = build_model_from_config(config)  # chainer
    dataset = read_tsv(args.dataset_path)
    output_path = args.output_path
    # dataset = dataset[:10]

    qa_dataset_size = len(dataset)
    logger.info('QA dataset size: {}'.format(qa_dataset_size))
    # n_queries = 0  # DEBUG
    start_time = time.time()
    TEXT_IDX = 1

    try:
        mapping = {}

        questions = [i['question'] for i in dataset]
        odqa_answers = odqa(questions)
        returned_top_n_size = len(odqa_answers[0])
        logger.info("Returned top n size: {}".format(returned_top_n_size))

        y_true = [([i['answer']], ['-1']) for i in dataset]
        y_pred = [(a[0][0], a[0][1]) for a in odqa_answers]

        recall_at = [1, 2, 3, 4, 5, 10]
        EM, F1 = np.zeros(shape=(max(recall_at),), dtype=np.float32), np.zeros(shape=(max(recall_at),),
                                                                               dtype=np.float32)

        for k in recall_at:
            for true_answer, top_answers in zip(y_true, odqa_answers):
                em, f1 = 0, 0
                for answer in top_answers[:k]:
                    a = answer[0]
                    em = max(em, exact_match([true_answer], [(a, 1)]))
                    f1 = max(f1, squad_f1([true_answer], [(a, 1)]))
                EM[k - 1] += em
                F1[k - 1] += f1
        EM = EM / len(questions)
        F1 = F1 / len(questions)
        for k in recall_at:
            print(f'recall@{k}: em: {EM[k-1]:.2f} f1: {F1[k-1]:.2f}')

        f1_top_1 = squad_f1(y_true, y_pred)
        em_top_1 = exact_match(y_true, y_pred)

        print(f'f1_top_1: {f1_top_1}')
        print(f'em_top_1: {em_top_1}')

        # for n in range(1, returned_top_n_size + 1):
        #     correct_answers = 0
        #     i = 0
        #     for qa, odqa_answer in zip(dataset, odqa_answers):
        #         true_id = int(qa['table_id'])
        #         pred_ids = odqa_answer[:n]
        #         correct_answers += int(true_id in pred_ids)
        #         # correct_answer = qa['answer']
        #         # texts = [answer[TEXT_IDX] for answer in ranker_answer[:n]]
        #         # correct_answers += instance_score([correct_answer], texts)
        #     print(correct_answers)
        #     total_score_on_top_i = correct_answers / qa_dataset_size
        #     logger.info(
        #         'Recall for top {}: {}'.format(n, total_score_on_top_i))
        #     mapping[n] = total_score_on_top_i

        logger.info("Completed successfully in {} seconds.".format(time.time() - start_time))
        logger.info("Quality mapping: {}".format(mapping))

    except Exception as e:
        logger.exception(e)
        logger.info("Completed with exception in {} seconds".format(time.time() - start_time))
        raise


if __name__ == "__main__":
    main()

