import os

import utils
import config
import logging
import numpy as np
from tqdm import tqdm
from data_process import Processor
from data_loader import Sentence
from model import BertSeg
from train import train, evaluate

from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader
from transformers.optimization import get_cosine_schedule_with_warmup, AdamW
from torch.nn.parallel import DistributedDataParallel
from torch.utils.data.distributed import DistributedSampler

import warnings

warnings.filterwarnings('ignore')


def dev_split(dataset_dir):
    """split dev set"""
    data = np.load(dataset_dir, allow_pickle=True)
    words = data["words"]
    labels = data["labels"]
    x_train, x_dev, y_train, y_dev = train_test_split(words, labels, test_size=config.dev_split_size, random_state=0)
    return x_train, x_dev, y_train, y_dev


def test():
    data = np.load(config.test_dir, allow_pickle=True)
    word_test = data["words"]
    label_test = data["labels"]
    test_dataset = Sentence(word_test, label_test, config)
    logging.info("--------Dataset Build!--------")
    # build data_loader
    test_loader = DataLoader(test_dataset, batch_size=config.batch_size,
                             shuffle=False, collate_fn=test_dataset.collate_fn)
    logging.info("--------Get Data-loader!--------")
    # Prepare model
    if config.model_dir is not None:
        # model = BertSeg.from_pretrained(config.model_dir)
        model = BertSeg.from_pretrained(config.roberta_model, num_labels=len(config.label2id))
        model.to(config.device)
        logging.info("--------Load model from {}--------".format(config.model_dir))
    else:
        logging.info("--------No model to test !--------")
        return
    val_metrics = evaluate(test_loader, model, mode='test')
    val_f1 = val_metrics['f1']
    val_p = val_metrics['p']
    val_r = val_metrics['r']
    logging.info("test loss: {}, f1 score: {}, precision: {}, recall: {}".
                 format(val_metrics['loss'], val_f1, val_p, val_r))


def load_dev(mode):
    if mode == 'train':
        # ??????????????????
        word_train, word_dev, label_train, label_dev = dev_split(config.train_dir)
    elif mode == 'test':
        train_data = np.load(config.train_dir, allow_pickle=True)
        dev_data = np.load(config.test_dir, allow_pickle=True)
        word_train = train_data["words"]
        label_train = train_data["labels"]
        word_dev = dev_data["words"]
        label_dev = dev_data["labels"]
    else:
        word_train = None
        label_train = None
        word_dev = None
        label_dev = None
    return word_train, word_dev, label_train, label_dev


def run():
    """train the model"""
    # set the logger
    utils.set_logger(config.log_dir)
    logging.info("device: {}".format(config.device))
    # ????????????????????????????????????
    processor = Processor(config)
    processor.process()
    logging.info("--------Process Done!--------")
    # ??????????????????
    word_train, word_dev, label_train, label_dev = load_dev('train')
    # build dataset
    train_dataset = Sentence(word_train, label_train, config)
    dev_dataset = Sentence(word_dev, label_dev, config)
    logging.info("--------Dataset Build!--------")
    # get dataset size
    train_size = len(train_dataset)
    # build data_loader
    train_loader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=False,
                              collate_fn=train_dataset.collate_fn, num_workers=0) # sampler=DistributedSampler(train_dataset),
    dev_loader = DataLoader(dev_dataset, batch_size=config.batch_size, shuffle=True,
                            collate_fn=dev_dataset.collate_fn, num_workers=0) # sampler=DistributedSampler(dev_dataset),
    logging.info("--------Get Dataloader!--------")
    # Prepare model
    device = config.device
    model = BertSeg.from_pretrained(config.roberta_model, num_labels=len(config.label2id))
    # ?????????model??????gpu???
    model = model.to(device)
    # Prepare optimizer
    if config.full_fine_tuning:
        # model.named_parameters(): [bert, classifier, crf]
        bert_optimizer = list(model.bert.named_parameters())
        classifier_optimizer = list(model.classifier.named_parameters())
        no_decay = ['bias', 'LayerNorm.bias', 'LayerNorm.weight']
        optimizer_grouped_parameters = [
            {'params': [p for n, p in bert_optimizer if not any(nd in n for nd in no_decay)],
             'weight_decay': config.weight_decay},
            {'params': [p for n, p in bert_optimizer if any(nd in n for nd in no_decay)],
             'weight_decay': 0.0},
            {'params': [p for n, p in classifier_optimizer if not any(nd in n for nd in no_decay)],
             'lr': config.learning_rate * 5, 'weight_decay': config.weight_decay},
            {'params': [p for n, p in classifier_optimizer if any(nd in n for nd in no_decay)],
             'lr': config.learning_rate * 5, 'weight_decay': 0.0},
            {'params': model.crf.parameters(), 'lr': config.learning_rate * 5}
        ]
    # only fine-tune the head classifier
    else:
        param_optimizer = list(model.classifier.named_parameters())
        optimizer_grouped_parameters = [{'params': [p for n, p in param_optimizer]}]
    optimizer = AdamW(optimizer_grouped_parameters, lr=config.learning_rate, correct_bias=False)
    train_steps_per_epoch = train_size // config.batch_size
    scheduler = get_cosine_schedule_with_warmup(optimizer,
                                                num_warmup_steps=2 * train_steps_per_epoch,
                                                num_training_steps=config.epoch_num * train_steps_per_epoch)

    # model = DistributedDataParallel(model, find_unused_parameters=True,
    #                                 device_ids=[config.local_rank], output_device=config.local_rank)
    # Train the model
    logging.info("--------Start Training!--------")
    for idx, batch_samples in enumerate(tqdm(train_loader)):
        batch_data, batch_token_starts, batch_labels, _ = batch_samples
        for i in range(len(batch_data)):
            if len(batch_data[i]) != len(batch_labels[i]) + 3:
                print("i: ", i)
                print("batch_data[i]: ", len(batch_data[i]))
                print("batch_labels[i]: ", len(batch_labels[i]))

    train(train_loader, dev_loader, model, optimizer, scheduler, config.model_dir)


if __name__ == '__main__':
    # if config.local_rank == 0:
    #     if os.path.exists(config.log_dir):
    #         os.remove(config.log_dir)
    run()
    # if config.local_rank == 0:
    # test()
