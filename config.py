import os
import torch

# bert_model = './pretrained_bert_models/bert-base-chinese/'
bert_model = './reference/pretrained_bert_models/bert-base-chinese/'
roberta_model = './reference/pretrained_bert_models/chinese-roberta-wwm-ext-large/'

model_dir = './reference/experiments/'
data_dir = './reference/data/'
# model_dir = './experiments/'
# data_dir = './data/'
train_dir = data_dir + 'training.npz'
test_dir = data_dir + 'test.npz'
files = ['training', 'test']
vocab_path = data_dir + 'vocab.npz'
exp_dir = './reference/experiments/'
case_dir = './reference/case/bad_case.txt'
# exp_dir = './experiments/'
# case_dir = './case/bad_case.txt'
log_dir = exp_dir + 'train.log'
output_dir = data_dir + 'output.txt'
res_dir = data_dir + 'res.txt'
test_ans = data_dir + 'test.txt'

max_vocab_size = 1000000
max_len = 510
sep_word = '@'  # 拆分句子的文本分隔符
sep_label = 'S'  # 拆分句子的标签分隔符

# 训练集、验证集划分比例
dev_split_size = 0.1

# 是否加载训练好的Seg模型
load_before = False

# 是否对整个BERT进行fine tuning
full_fine_tuning = True

# hyper-parameter
learning_rate = 1e-5
weight_decay = 0.01
clip_grad = 5

batch_size = 4
epoch_num = 20
min_epoch_num = 5
patience = 0.0002
patience_num = 4

len_tokenizer = 768

gpu = 'cuda'

if gpu == 'cuda':
    # torch.distributed.init_process_group(backend='nccl')
    # local_rank = torch.distributed.get_rank()
    # torch.cuda.set_device(local_rank)
    # device = torch.device("cuda", local_rank)
    device = torch.device("cuda")
else:
    device = torch.device("cpu")

# B：分词头部 M：分词词中 E：分词词尾 S：独立成词
label2id = {'B': 0, 'M': 1, 'E': 2, 'S': 3}

id2label = {_id: _label for _label, _id in list(label2id.items())}
