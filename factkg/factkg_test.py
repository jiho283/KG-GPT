import argparse
import json
import os
import time
import re
import openai
import tqdm
import shortuuid
import pickle


def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()


def claim_divider_parse_answer(answer, gt_entities):
    processed_answer_set = {}
    answer = answer.strip()
    splitted_answers = answer.split('\n')
    all_entities = []
    try:
        for nth_answer in splitted_answers:
            nth_answer = nth_answer.strip()
            for i in range(3):
                if str(i+1)+'. ' in nth_answer[:5]:
                    temp_ans = nth_answer.split(str(i+1)+'. ')[1]
                    temp_split = temp_ans.split(', Entity set: ')
                    sentence = temp_split[0]
                    
                    entity_set = temp_split[1]
                    entity_set = entity_set.split('[')[1]
                    entity_set = entity_set.split(']')[0]
                    entity_set = entity_set.split(' ## ')
                    
                    new_entity_set = []
                    for ent in entity_set:
                        new_entity_set.append(ent[1:-1])
                        all_entities.append(ent[1:-1])
                    break
            processed_answer_set[sentence] = new_entity_set
    except:
        return None

    return processed_answer_set


def relation_candidates(KG, type_dict, entity_set):
    final_type_set = []
    final_entity_set = []
    new_entity_set = []
    for ent in entity_set:
        if '"' in ent:
            final_entity_set.append(ent)
            new_entity_set.append(ent)
            continue
        total = []
        ent = ent.strip()
        splitted_ent = ent.split(' ')
        if len(splitted_ent) == 1:
            splitted_ent = ent.split('_')
        for spl_ent in splitted_ent:
            total.append([spl_ent.strip(), spl_ent.strip()[0].upper() + spl_ent.strip()[1:]])

        temp_list = []
        for chunk in total:
            if len(temp_list) == 0:
                temp_list = [chunk[0], chunk[1]]
                continue
            new_list = []
            for temp in temp_list:
                new_list.append(temp+chunk[0])
                new_list.append(temp+chunk[1])
            
            temp_list = new_list.copy()
        
        is_type = 0
        for type_ in temp_list:
            try:
                a = type_dict[type_]
                final_type_set.append([type_])
                new_entity_set.append(type_)
                is_type = 1
                break
            except:
                continue

        if is_type == 0:
            final_entity_set.append(ent)
            new_entity_set.append(ent)

    #### For type relations
    all_type_list = []
    if len(final_type_set) == 1:
        for temp_type in final_type_set[0]:
            for type_temp_ele in list(type_dict[temp_type]):
                all_type_list += type_dict[temp_type][type_temp_ele]
        all_type_list = list(set(all_type_list))
    else:
        for final_set in final_type_set:
            temp_all_type_list = []
            for other_final_set in final_type_set:
                if final_set != other_final_set:
                    for final_ele in final_set:
                        for other_ele in other_final_set:
                            if len(temp_all_type_list) == 0:
                                try:
                                    temp_all_type_list = type_dict[final_ele][other_ele]
                                except:
                                    temp_all_type_list = []
                            else:
                                try:
                                    temp_all_type_list = [id_type for id_type in temp_all_type_list if id_type in type_dict[final_ele][other_ele]]
                                except:
                                    temp_all_type_list = []
            temp_all_type_list_copy = temp_all_type_list.copy()
            all_type_list += temp_all_type_list_copy
        all_type_list = list(set(all_type_list))

    #### For entity relations
    all_entity_list = []
    if len(final_entity_set) == 1:
        try:
            all_entity_list = list(KG[final_entity_set[0]])
        except:
            all_entity_list = []
    else:
        for final_entity in final_entity_set:
            for another_final_entity in final_entity_set:
                if final_entity != another_final_entity:
                    try:
                        for temp_rel in list(KG[final_entity]):
                            try:
                                another_final_list = list(KG[another_final_entity])
                                if '~' in temp_rel[0]:
                                    if temp_rel.split('~')[1] in another_final_list:
                                        all_entity_list.append(temp_rel.split('~')[1])
                                    elif '~' + temp_rel in another_final_list:
                                        all_entity_list.append(temp_rel)
                            except:
                                pass
                    except:
                        pass
        all_entity_list = list(set(all_entity_list))

    final_relation_list = []
    
    if len(all_type_list) == 0:
        for rel in all_entity_list:
            if '~' in rel[0]:
                final_relation_list.append(rel.split('~')[1])
            else:
                final_relation_list.append(rel)
    
    elif len(all_entity_list) == 0:
        for rel in all_type_list:
            if '~' in rel[0]:
                final_relation_list.append(rel.split('~')[1])
            else:
                final_relation_list.append(rel)
    
    else:
        for rel in all_entity_list:
            if '~' in rel[0]:
                if rel.split('~')[1] in all_type_list:
                    final_relation_list.append(rel.split('~')[1])
            elif rel in all_type_list or '~'+rel in all_type_list or len(all_type_list) == 0:
                final_relation_list.append(rel)
    
    return final_relation_list, new_entity_set


def retrieval_relation_parse_answer(answer):
    pattern = r'\[[^\]]+\]'
    matches = re.findall(pattern, answer)
    
    if len(matches) != 1:
        return None
    
    # Extract the components from the matches and flatten the list
    components = [component.strip() for match in matches for component in match.strip('[]').split(',')]
    components = [component.strip("''") if "'" in component else component for component in components ]
    return components


def graph_extractor(target_list):
    if len(target_list) == 0:
        return target_list
    
    return_list = []
    filter_dict = {'head': {}, 'tail':{}}
    return_list.append(target_list[0])
    used_heads = []
    used_tails = []
    filter_dict['head'][target_list[0][0]] = [target_list[0][1]]
    filter_dict['tail'][target_list[0][2]] = [target_list[0][1]]
    used_heads.append(target_list[0][0])
    used_tails.append(target_list[0][2])
    
    for tar in target_list:
        if tar in return_list:
            continue
        else:
            try:
                if tar[1] in filter_dict['head'][tar[0]]:
                    continue
            except:
                try:
                    if tar[1] in filter_dict['tail'][tar[2]]:
                        continue
                except:
                    pass
            try:
                if tar[1] not in list(filter_dict['head'][tar[0]]):
                    filter_dict['head'][tar[0]] = [tar[1]]
                    try:
                        filter_dict['tail'][tar[2]].append(tar[1])
                    except:
                        filter_dict['tail'][tar[2]] = [tar[1]]
                    return_list.append(tar)
                    continue
            except:
                pass

            try:
                if tar[1] not in list(filter_dict['tail'][tar[2]]):
                    filter_dict['tail'][tar[2]] = [tar[1]]
                    try:
                        filter_dict['head'][tar[0]].append(tar[1])
                    except:
                        filter_dict['head'][tar[0]] = [tar[1]]
                    return_list.append(tar)
                    continue
            except:
                pass
            
            if tar[2] in used_heads or tar[0] in used_tails:
                return_list.append(tar)
                try:
                    filter_dict['head'][tar[0]].append(tar[1])
                except:
                    filter_dict['head'][tar[0]] = [tar[1]]
                try:
                    filter_dict['tail'][tar[2]].append(tar[1])
                except:
                    filter_dict['tail'][tar[2]] = [tar[1]]
    return return_list


def get_answer(model_name: str, qid: int, claim: str, gt_entities: list, KG: dict, type_dict: dict, top_k: int, max_tokens: int):
    ans = {
        "answer_id": shortuuid.uuid(),
    }

    sentence_divide_query = open_file('./prompts/sentence_divide_prompt.txt').replace('<<<<CLAIM>>>>', claim).replace('<<<<ENTITY_SET>>>>', str(gt_entities))
    
    #### 1. sentence divide
    for _ in range(3):
        try:
            response = openai.ChatCompletion.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {
                        "role": "user",
                        "content": sentence_divide_query,
                    },
                ],
                max_tokens=max_tokens,
                temperature=0.2,
                top_p = 0.1
            )
            divide_claim_result = response["choices"][0]["message"]["content"]
            
            divided_claim_list = claim_divider_parse_answer(divide_claim_result, gt_entities)
            if divided_claim_list:
                break
        except Exception as e:
            print("[ERROR]", e)
            time.sleep(5)
    with open(f'./generated_prompts/{qid}_sentence_divide.pickle', 'wb') as f:
        pickle.dump(divided_claim_list, f)


    used_all_relations = []
    #### 2. Relation Retrieval
    total_evidence = []
    for divided_claim, corresponding_entity_set in divided_claim_list.items():
        rel_candidates, corresponding_entity_set = relation_candidates(KG, type_dict, corresponding_entity_set)
        relation_retrieval_query = open_file('./prompts/relation_retrieval_prompt.txt').replace('<<<<TOP_K>>>>', str(top_k)).replace('<<<<SENTENCE>>>>', divided_claim).replace('<<<<RELATION_SET>>>>', str(rel_candidates))
        
        if len(rel_candidates) < top_k:
            used_all_relations += rel_candidates
            total_triples = []
            for ret_rel in rel_candidates:
                if len(corresponding_entity_set) == 1:
                    total_triples.append([corresponding_entity_set[0], ret_rel])
                    total_triples.append([corresponding_entity_set[0], '~'+ret_rel])
                for fir_id in range(len(corresponding_entity_set)):
                    for sec_id in range(len(corresponding_entity_set)):
                        if fir_id != sec_id:
                            total_triples.append([corresponding_entity_set[fir_id], ret_rel, corresponding_entity_set[sec_id]])
                            total_triples.append([corresponding_entity_set[fir_id], '~'+ret_rel, corresponding_entity_set[sec_id]])
            if len(total_triples) > 0:
                total_evidence.append(total_triples)
            continue
        

        for _ in range(3):
            try:
                response = openai.ChatCompletion.create(
                     model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {
                            "role": "user",
                            "content": relation_retrieval_query,
                        },
                    ],
                    max_tokens=max_tokens,
                    temperature=0.2,
                    top_p = 0.1
                )
                relation_retrieval_result = response["choices"][0]["message"]["content"]
                retrieved_relations = retrieval_relation_parse_answer(relation_retrieval_result)

                if retrieved_relations:
                    used_all_relations += retrieved_relations
                    break
                print(_, 'th try!')
            except Exception as e:
                print("[ERROR]", e)
                time.sleep(5)
        
        total_triples = []
        for ret_rel in retrieved_relations:
            if len(corresponding_entity_set) == 1:
                total_triples.append([corresponding_entity_set[0], ret_rel])
                total_triples.append([corresponding_entity_set[0], '~'+ret_rel])

            for fir_id in range(len(corresponding_entity_set)):
                for sec_id in range(len(corresponding_entity_set)):
                    if fir_id != sec_id:
                        total_triples.append([corresponding_entity_set[fir_id], ret_rel, corresponding_entity_set[sec_id]])
                        total_triples.append([corresponding_entity_set[fir_id], '~'+ret_rel, corresponding_entity_set[sec_id]])
        total_evidence.append(total_triples)

    ### for three hop
    additional = []
    for evi_set in total_evidence:
        try:
            a = type_dict[evi_set[0][0]] 
            b = type_dict[evi_set[0][2]]
            for trip in evi_set:
                additional.append(trip[1]) 
        except:
            continue

    before_final = []
    for evi_set in total_evidence:
        before_final_evi = []
        for trip in evi_set:
            try:
                a = type_dict[trip[0]]
                continue
            except:
                try:
                    b = type_dict[trip[2]]
                    try:
                        tails = KG[trip[0]][trip[1]]
                        for tail in tails:
                            before_final_evi.append([trip[0], trip[1], tail])
                    except:
                        continue
                except:
                    try:
                        if len(trip) == 2:
                            before_final_evi.append(trip)
                        elif trip[2] in KG[trip[0]][trip[1]]:
                            before_final_evi.append(trip)
                    except:
                        pass
        if len(before_final_evi) > 0:
            before_final.append(before_final_evi)

    final_evidence = []
    for chunk in before_final:
        find_gt = 0
        for trip in chunk:
            if len(trip) != 2 and trip[0] in gt_entities and trip[2] in gt_entities:
                final_evidence.append(trip)
                find_gt = 1
        
        if find_gt == 1:
            continue

        if len(before_final) == 1:
            for trip in chunk:
                if len(trip) == 2:
                    try:
                        tails = KG[trip[0]][trip[1]]
                        for tail in tails:
                            final_evidence.append([trip[0], trip[1], tail])
                    except:
                        continue
            break
        
        additional = list(set(additional))
        
        if len(additional) != 0:
            for sec_chunk in before_final:
                if chunk == sec_chunk:
                    continue
                for trip in chunk:
                    if len(trip) == 2:
                        continue
                    for sec_trip in sec_chunk:
                        if len(sec_trip) == 2:
                            continue
                        for rel_ in additional:
                            for trip_id in [0, 2]:
                                for sec_trip_id in [0, 2]:
                                    for rel_add in ['', '~']:
                                        try:
                                            if rel_add == '' and '~' in rel_:
                                                if trip[trip_id] in KG[sec_trip[sec_trip_id]][rel_.split('~')[1]]:
                                                    final_evidence.append(trip)
                                                    final_evidence.append(sec_trip)
                                                    final_evidence.append([sec_trip[sec_trip_id], rel_.split('~')[1], trip[trip_id]])
                                        except:
                                            pass
                                        try:
                                            if trip[trip_id] in KG[sec_trip[sec_trip_id]][rel_add + rel_]:
                                                final_evidence.append(trip)
                                                final_evidence.append(sec_trip)
                                                final_evidence.append([sec_trip[sec_trip_id], rel_add + rel_, trip[trip_id]])
                                        except:
                                            pass
        else:
            for sec_chunk in before_final:
                if chunk == sec_chunk:
                    continue
                for trip in chunk:
                    for sec_trip in sec_chunk:
                        if len(trip) == 2 or len(sec_trip) == 2:
                            continue
                        if (trip[0] in sec_trip and trip[0] not in gt_entities) or (trip[2] in sec_trip and trip[2] not in gt_entities):
                            final_evidence.append(trip)
                            final_evidence.append(sec_trip)
    
    #### Remove duplicated triples
    new_final_evidence = []
    if len(final_evidence) != 0:
        for trip in final_evidence:
            if '~' in trip[1]:
                if [trip[2], trip[1].split('~')[1], trip[0]] not in new_final_evidence and [trip[2], trip[1].split('~')[1], trip[0]] not in final_evidence:
                    new_final_evidence.append([trip[2], trip[1].split('~')[1], trip[0]])
                    continue
            else:
                if trip not in new_final_evidence:
                    new_final_evidence.append(trip)
    
    new_final_evidence = graph_extractor(new_final_evidence)
    with open(f'./generated_prompts/{qid}_final_evidence.pickle', 'wb') as f:
        pickle.dump(new_final_evidence, f)

    #### Verification phase
    verify_prompt = open_file('./prompts/verify_claim_with_evidence.txt').replace('<<<<CLAIM>>>>', claim).replace('<<<<EVIDENCE_SET>>>>', str(new_final_evidence)).replace('<<<<ENTITY_SET>>>>', str(gt_entities)).replace('<<<<RELATION_SET>>>>', str(used_all_relations))
    for _ in range(3):
        try:
            response = openai.ChatCompletion.create(
                 model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {
                        "role": "user",
                        "content": verify_prompt,
                    },
                ],
                max_tokens=max_tokens,
                temperature=0.2,
                top_p = 0.1
            )
            verification = response["choices"][0]["message"]["content"]

            if ('true' in verification.lower() and 'false' not in verification.lower()) or ('not refute' in verification.lower() and 'not support' not in verification.lower()) or ('support' in verification.lower() and 'refute' not in verification.lower()):
                return True, verification
            elif ('false' in verification.lower() and 'true' not in verification.lower()) or ('not support' in verification.lower() and 'not refute' not in verification.lower()) or ('refute' in verification.lower() and 'support' not in verification.lower()):
                return False, verification
            else:
                continue
                
        except Exception as e:
            print("[ERROR]", e)
            time.sleep(5)
    
    return 'Another Answer', verification


if __name__ == "__main__":

    openai.api_key = open_file('./openai_api_key.txt')
    parser = argparse.ArgumentParser(description="Parsing input arguments.")
    parser.add_argument('--model', type=str, required=True, help='Model name. gpt-4 or gpt-3.5-turbo-0613')
    parser.add_argument('--kg', type=str, required=True, help='Path for KG.')
    
    args = parser.parse_args()

    model_name = args.model
    kg_path = args.kg

    print('Start!!!')
    with open(kg_path, 'rb') as f:
        dbp = pickle.load(f)

    print('Data loading done!!!')
    with open('./type_dict.pickle', 'rb') as f:
        type_dict = pickle.load(f)
    
    futures = []
    start_token = 0
    
    ####For new experiment, use it.
    result = {}
    questions_dict = {}
    entity_set_dict = {}
    label_set_dict = {}
    with open(os.path.expanduser(f"./extracted_test_set.jsonl")) as f:
        for line in f:
            if not line:
                continue
            q = json.loads(line)
            questions_dict[q["question_id"]] = q["question"]
            entity_set_dict[q["question_id"]] = q["entity_set"]
            label_set_dict[q["question_id"]] = q["Label"]

    ####For new experiment, use it.
    # with open(f'./result.pickle', 'rb') as f:
    #     result = pickle.load(f)
    
    Correct = []
    Wrong = []
    Error = []
    Another = []

    for qid, question in questions_dict.items():
        ####For new experiment, use it.
        # try:
        #     test_value = result[qid]
        #     continue
        # except:
        #     pass
        if qid == 3532: ## Timeout
            Error.append(qid)
            print(qid, ': Error...')
            result[qid] = 'Error'
            continue
        try:                
            future = get_answer(model_name, qid, question, entity_set_dict[qid], KG=dbp, type_dict=type_dict, top_k = 5, max_tokens=1024)
            futures.append(future)
            if future[0] == 'Another Answer':
                Another.append(qid)
                print(qid, ': ', future[1])
                result[qid] = future[1]
            elif future[0] == label_set_dict[qid][0]:
                Correct.append(qid)
                print(qid, ': Correct!')
                result[qid] = 'Correct'
            else:
                Wrong.append(qid)
                print(qid, ': Wrong...')
                result[qid] = 'Wrong'
        except:
            Error.append(qid)
            print(qid, ': Error...')
            result[qid] = 'Error'
        with open(f'./result.pickle', 'wb') as f:
            pickle.dump(result, f)
    
    tot_corr = 0
    for tot_id in list(result):
        if result[tot_id] == 'Correct':
            tot_corr += 1
    
    print('Accuracy: ', tot_corr/len(list(result)))
