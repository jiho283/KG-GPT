# KG-GPT: A General Framework for Reasoning on Knowledge Graphs Using Large Language Models
We propose KG-GPT, a multi-purpose framework leveraging LLMs for tasks employing KGs. KG-GPT comprises three steps: Sentence Segmentation, Graph Retrieval, and Inference, each aimed at partitioning sentences, retrieving relevant graph components, and deriving logical conclusions, respectively. We evaluate KG-GPT using KG-based fact verification and KGQA benchmarks, with the model showing competitive and robust performance, even outperforming several fully-supervised models. Our work, therefore, marks a significant step in unifying structured and unstructured data processing within the realm of LLMs.

The code is released along with our [paper](https://arxiv.org/abs/2310.11220) (EMNLP 2023 Findings). For further details, please refer to our paper.

You can download FactKG from [this link](https://github.com/jiho283/FactKG) and MetaQA from [this link](https://github.com/yuyuz/MetaQA).

## Before starting: Enter OpenAI API key
Write your own OpenAI API key in ```factkg/openai_api_key.txt``` and ```metaqa/openai_api_key.txt``` and save them.

## 1. FactKG
```cd factkg```
### 1-1) Preprocess
1. ```python data/preprocess.py --factkg_test /path/to/factkg_test.pickle```

2. ```python data/make_type_dict.py --kg /path/to/dbpedia_2015_undirected.pickle --relations /path/to/relations_for_final.pickle```

### 1-2) Inference
```python factkg_test.py --model gpt-3.5-turbo-0613 --kg /path/to/dbpedia_2015_undirected.pickle```


## 2. MetaQA
```cd metaqa```

### 2-1) Preprocess
```python data/preprocess.py --test_1_hop /path/to/1-hop/vanilla/qa_test.txt --test_2_hop /path/to/2-hop/vanilla/qa_test.txt --test_3_hop /path/to/3-hop/vanilla/qa_test.txt --kb /path/to/kb.txt```

### 2-2) Inference
1-hop: ```python metaqa_1hop_test.py```

2-hop: ```python metaqa_2hop_test.py```

3-hop: ```python metaqa_3hop_test.py```
