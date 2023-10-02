import json
import jsonlines
import pickle
import argparse

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Parsing input arguments.")
    parser.add_argument('--factkg_test', type=str, required=True, help='Path for factkg test set.')
    
    args = parser.parse_args()

    test_set_path = args.factkg_test

    with open(test_set_path, 'rb') as f:
        test_set = pickle.load(f)

    claims = list(test_set)

    with jsonlines.open(f'./extracted_test_set.jsonl', mode='w') as w:
        for i, sample in enumerate(claims):
            new_sample = {}
            new_sample["question_id"] = i+1
            new_sample["question"] = sample
            new_sample["types"] = test_set[sample]["types"]
            new_sample["entity_set"] = test_set[sample]["Entity_set"]
            new_sample["Label"] = test_set[sample]["Label"]
            w.write(new_sample)