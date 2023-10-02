import pickle
from tqdm import tqdm
import argparse

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Parsing input arguments.")
    parser.add_argument('--kg', type=str, required=True, help='Path for KG.')
    parser.add_argument('--relations', type=str, required=True, help='Path for the relations list.')
    
    args = parser.parse_args()

    kg_path = args.kg
    relations_path = args.relations

    print('Start!')
    with open(kg_path, 'rb') as f:
        dbp = pickle.load(f)
    
    with open(relations_path, 'rb') as f:
        relations = pickle.load(f)
    
    entities = list(dbp)

    relation_set = {}
    for rel in relations:
        if '~' not in rel[0]:
            relation_set[rel] = 0
    print('Data loading done!')

    total_result = {}
    for ent in tqdm(entities):
        try:
            bpl = dbp[ent]
            rels = list(bpl)
            head_types = bpl['22-rdf-syntax-ns#type']
        except:
            continue
        if len(rels) == 1 and 'rdf-schema#label' in rels:
            continue
        
        for rel in rels:
            tails = bpl[rel]
            for tail in tails:
                if '"' in tail:
                    continue
                try:
                    tail_types = dbp[tail]['22-rdf-syntax-ns#type']
                    a = relation_set[rel]
                except:
                    continue

                for head_type in head_types:
                    for tail_type in tail_types:
                        try:
                            total_result[head_type][tail_type][rel] = 0
                        except:
                            try:
                                total_result[head_type][tail_type] = {}
                                total_result[head_type][tail_type][rel] = 0
                            except:
                                total_result[head_type] = {}
                                total_result[head_type][tail_type] = {}
                                total_result[head_type][tail_type][rel] = 0

    with open('./type_dict.pickle', 'wb') as f:
        pickle.dump(total_result, f)