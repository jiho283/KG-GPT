import pickle
import json
import jsonlines
import argparse
import re

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Parsing input arguments.")
    parser.add_argument('--test_1_hop', type=str, required=True, help='Path for metaqa 1-hop test set.')
    parser.add_argument('--test_2_hop', type=str, required=True, help='Path for metaqa 2-hop test set.')
    parser.add_argument('--test_3_hop', type=str, required=True, help='Path for metaqa 3-hop test set.')
    parser.add_argument('--kb', type=str, required=True, help='Path for metaqa kb.')
    
    args = parser.parse_args()

    test_1_hop = args.test_1_hop
    test_2_hop = args.test_2_hop
    test_3_hop = args.test_3_hop
    kb = args.kb

    KG_construct = {}
    with open(kb, 'r') as f:
        for line in f:
            head = line.strip().split('|')[0]
            relation = line.strip().split('|')[1]
            tail = line.strip().split('|')[2]

            try:
                KG_construct[head][relation].append(tail)
            except:
                try:
                    KG_construct[head][relation] = [tail]
                except:
                    KG_construct[head] = {}
                    KG_construct[head][relation] = [tail]

            try:
                KG_construct[tail]['~'+relation].append(head)
            except:
                try:
                    KG_construct[tail]['~'+relation] = [head]
                except:
                    KG_construct[tail] = {}
                    KG_construct[tail]['~'+relation] = [head]

    with open('data/metaqa_kg.pickle', 'wb') as f:
        pickle.dump(KG_construct, f)
    

    onehop = {}
    with open(test_1_hop, 'r') as f:
        for line in f:
            seperated = line.strip().split('\t')
            entities = re.findall(r'\[(.*?)\]', seperated[0])
            labels = seperated[1]
            labels = labels.split('|')
            onehop[seperated[0]+'?'] = {'entity_set': [entities[0]], 'Label': labels}

    with jsonlines.open(f'data/onehop_test_set.jsonl', mode='w') as w:
        total = 0
        for i, sample in enumerate(list(onehop)):
            new_sample = {}
            new_sample["question_id"] = i+1
            new_sample["question"] = sample
            new_sample["entity_set"] = onehop[sample]["entity_set"]
            new_sample["Label"] = onehop[sample]["Label"]
            w.write(new_sample)
    

    twohop = {}
    with open(test_2_hop, 'r') as f:
        for line in f:
            seperated = line.strip().split('\t')
            entities = re.findall(r'\[(.*?)\]', seperated[0])
            labels = seperated[1]
            labels = labels.split('|')
            twohop[seperated[0]+'?'] = {'entity_set': [entities[0]], 'Label': labels}

    with jsonlines.open(f'data/twohop_test_set.jsonl', mode='w') as w:
        total = 0
        for i, sample in enumerate(list(twohop)):
            new_sample = {}
            new_sample["question_id"] = i+1
            new_sample["question"] = sample
            new_sample["entity_set"] = twohop[sample]["entity_set"]
            new_sample["Label"] = twohop[sample]["Label"]
            w.write(new_sample)
    

    threehop = {}
    with open(test_3_hop, 'r') as f:
        for line in f:
            seperated = line.strip().split('\t')
            entities = re.findall(r'\[(.*?)\]', seperated[0])
            labels = seperated[1]
            labels = labels.split('|')
            threehop[seperated[0]+'?'] = {'entity_set': [entities[0]], 'Label': labels}

    with jsonlines.open(f'data/threehop_test_set.jsonl', mode='w') as w:
        total = 0
        for i, sample in enumerate(list(threehop)):
            new_sample = {}
            new_sample["question_id"] = i+1
            new_sample["question"] = sample
            new_sample["entity_set"] = threehop[sample]["entity_set"]
            new_sample["Label"] = threehop[sample]["Label"]
            w.write(new_sample)
