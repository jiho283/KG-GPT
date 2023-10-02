import argparse
import json
import os
import time
import concurrent.futures
import re
import openai
import tqdm
import shortuuid
import pickle

def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()


def save_file(filepath, content):
    with open(filepath, 'w', encoding='utf-8') as outfile:
        outfile.write(content)


def claim_divider_parse_answer(answer, gt_entity):
    processed_answer_set = {}
    answer = answer.strip()
    splitted_answers = answer.split('\n')

    try:
        for nth_answer in splitted_answers:
            nth_answer = nth_answer.strip()
            for i in range(5):
                if str(i+1)+'. ' in nth_answer[:5]:
                    temp_ans = nth_answer.split(str(i+1)+'. ')[1]
                    temp_split = temp_ans.split(', Entity set: ')
                    sentence = temp_split[0]
                    
                    entity_set = temp_split[1]
                    entity_set = entity_set.split('[')[1]
                    entity_set = entity_set.split(']')[0]
                    new_entity_set = []
                    if len(entity_set) == 1 or len(entity_set) == 2:
                        new_entity_set.append(entity_set)
                    elif '"' in entity_set[0] or "'" in entity_set[0]:
                        new_entity_set.append(entity_set[1:-1])
                    else:
                        new_entity_set.append(entity_set)
                    break
            processed_answer_set[sentence] = new_entity_set
    except:
        processed_answer_set[sentence] = [gt_entity]

    return processed_answer_set


def retrieval_relation_parse_answer(answer):
    pattern = r'\[[^\]]+\]'

    matches = re.findall(pattern, answer)
    
    if len(matches) != 1:
        return None
    
    # Extract the components from the matches and flatten the list
    components = [component.strip() for match in matches for component in match.strip('[]').split(',')]

    components = [component.strip("''") if "'" in component else component for component in components ]
    return components


def get_answer(qid: int, claim: str, gt_entity: str, KG: dict, top_k: int, max_tokens: int):
    ans = {
        "answer_id": shortuuid.uuid(),
    }
    entities = re.findall(r'\[(.*?)\]', claim)
    sentence_divide_query = open_file('./meta_1hop_prompts/sentence_divide_prompt.txt').replace('<<<<CLAIM>>>>', claim).replace('<<<<ENTITY_SET>>>>', '['+entities[0]+']')
    
    #### 1. sentence divide
    for _ in range(5):
        try:
            response = openai.ChatCompletion.create(
                 model="gpt-3.5-turbo-0613",
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
            divided_claim_list = claim_divider_parse_answer(divide_claim_result, gt_entity)
            break
        except Exception as e:
            print("[ERROR]", e)
            time.sleep(5)
    with open(f'./meta_generated_prompts/1hop/{qid}_sentence_divide.pickle', 'wb') as f:
        pickle.dump(divided_claim_list, f)
        
    used_all_relations = []
    #### 2. Relation Retrieval
    total_evidence = []
    start_relation = []
    extra_relation = []
    for divided_claim, corresponding_entity_set in divided_claim_list.items():
        one_hop_relation_set = list(KG[gt_entity])
        all_relation_set = []
        for one_rel in list(KG[gt_entity]):
            all_relation_set.append(one_rel)
            one_tails = KG[gt_entity][one_rel]
            for one_tail in one_tails:
                two_rels = list(KG[one_tail])
                for two_rel in two_rels:
                    all_relation_set.append(two_rel)
                    two_tails = KG[one_tail][two_rel]
                    for two_tail in two_tails:
                        three_rels = list(KG[two_tail])
                        all_relation_set += three_rels
        all_relation_set = list(set(all_relation_set))
        new_all_relation_set = []

        for tar_rel in all_relation_set:
            if tar_rel in new_all_relation_set:
                continue
            if '~' in tar_rel:
                new_all_relation_set.append(tar_rel.split('~')[1])
            else:
                new_all_relation_set.append(tar_rel)
        new_all_relation_set = list(set(new_all_relation_set))
        
        if len(corresponding_entity_set) == 1:
            if len(list(KG[corresponding_entity_set[0]])) == 1:
                start_relation.append(one_hop_relation_set)
                continue
            else:
                relation_retrieval_query = open_file('./meta_1hop_prompts/relation_retrieval_prompt.txt').replace('<<<<TOP_K>>>>', str(top_k)).replace('<<<<SENTENCE>>>>', divided_claim).replace('<<<<RELATION_SET>>>>', str(one_hop_relation_set))
        else:
            relation_retrieval_query = open_file('./meta_1hop_prompts/relation_retrieval_prompt.txt').replace('<<<<TOP_K>>>>', str(top_k)).replace('<<<<SENTENCE>>>>', divided_claim).replace('<<<<RELATION_SET>>>>', str(new_all_relation_set))
        
        for _ in range(5):
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo-0613",
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
                    break
                print(_, 'th try!')
            except Exception as e:
                print("[ERROR]", e)
                time.sleep(5)

        if len(corresponding_entity_set) == 1:
            start_relation.append(retrieved_relations)
        else:
            extra_relation.append(retrieved_relations)

    final_evidence = []
    if len(extra_relation) == 0:
        for rel in start_relation[0]:
            try:
                tails = KG[gt_entity][rel]
                for tail in tails:
                    final_evidence.append([gt_entity, rel, tail])
            except:
                pass

            try:
                tails = KG[gt_entity]['~'+rel]
                for tail in tails:
                    final_evidence.append([tail, rel, gt_entity])
            except:
                pass

    elif len(extra_relation) == 1:
        for fir_rev in ['', '~']:
            for sec_rev in ['', '~']:
                for rel in start_relation[0]:
                    for sec_rel in extra_relation[0]:
                        try:
                            tails = KG[gt_entity][fir_rev+rel]
                            for tail in tails:
                                try:
                                    hop_2_tails = KG[tail][sec_rev+sec_rel]
                                    for hop_2_tail in hop_2_tails:
                                        if fir_rev == '':
                                            final_evidence.append([gt_entity, rel, tail])
                                        else:
                                            final_evidence.append([tail, rel, gt_entity])
                                        if sec_rev == '':
                                            final_evidence.append([tail, sec_rel, hop_2_tail])
                                        else:
                                            final_evidence.append([hop_2_tail, sec_rel, tail])
                                except:
                                    pass
                        except:
                            pass

    else:
        for fir_rev in ['', '~']:
            for sec_rev in ['', '~']:
                for thr_rev in ['', '~']:
                    for rel in start_relation[0]:
                        for sec_rel in extra_relation[0]:
                            for thr_rel in extra_relation[1]:
                                try:
                                    tails = KG[gt_entity][fir_rev+rel]
                                    for tail in tails:
                                        try:
                                            hop_2_tails = KG[tail][sec_rev+sec_rel]
                                            for hop_2_tail in hop_2_tails:
                                                try:
                                                    hop_3_tails = KG[hop_2_tail][thr_rev+thr_rel]
                                                    for hop_3_tail in hop_3_tails:
                                                        if fir_rev == '':
                                                            final_evidence.append([gt_entity, rel, tail])
                                                        else:
                                                            final_evidence.append([tail, rel, gt_entity])
                                                        if sec_rev == '':
                                                            final_evidence.append([tail, sec_rel, hop_2_tail])
                                                        else:
                                                            final_evidence.append([hop_2_tail, sec_rel, tail])
                                                        if thr_rev == '':
                                                            final_evidence.append([hop_2_tail, thr_rel, hop_3_tail])
                                                        else:
                                                            final_evidence.append([hop_3_tail, thr_rel, hop_2_tail])
                                            
                                                except:
                                                    pass
                                        except:
                                            pass
                                        try:
                                            hop_2_tails = KG[tail][thr_rev+thr_rel]
                                            for hop_2_tail in hop_2_tails:
                                                try:
                                                    hop_3_tails = KG[hop_2_tail][sec_rev+sec_rel]
                                                    for hop_3_tail in hop_3_tails:
                                                        if fir_rev == '':
                                                            final_evidence.append([gt_entity, rel, tail])
                                                        else:
                                                            final_evidence.append([tail, rel, gt_entity])
                                                        if thr_rev == '':
                                                            final_evidence.append([tail, thr_rel, hop_2_tail])
                                                        else:
                                                            final_evidence.append([hop_2_tail, thr_rel, tail])
                                                        if sec_rev == '':
                                                            final_evidence.append([hop_2_tail, sec_rel, hop_3_tail])
                                                        else:
                                                            final_evidence.append([hop_3_tail, sec_rel, hop_2_tail])
                                            
                                                except:
                                                    pass
                                        except:
                                            pass
                                except:
                                    pass
    
    
    new_final_evidence = []

    for evi in final_evidence:
        if evi in new_final_evidence:
            continue
        if '~' in evi[1]:
            if [evi[2], evi[1].split('~')[1], evi[0]] not in new_final_evidence:
                new_final_evidence.append([evi[2], evi[1].split('~')[1], evi[0]])
        else:
            new_final_evidence.append([evi[0], evi[1], evi[2]])
    with open(f'./meta_generated_prompts/1hop/{qid}_final_evidence.pickle', 'wb') as f:
        pickle.dump(new_final_evidence, f)

    #### Verification phase
    verify_prompt = open_file('./meta_1hop_prompts/verify_claim_with_evidence.txt').replace('<<<<CLAIM>>>>', claim).replace('<<<<EVIDENCE_SET>>>>', str(new_final_evidence))
    for _ in range(5):
        try:
            response = openai.ChatCompletion.create(
                 model="gpt-3.5-turbo-0613",
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
            save_file(f'./meta_generated_prompts/1hop/{qid}_verification_result.txt', verification)

            return verification.lower()
                
        except Exception as e:
            print("[ERROR]", e)
            time.sleep(5)
    
    return 'Error'


if __name__ == "__main__":

    openai.api_key = open_file('./openai_api_key.txt')

    print('Start!!!')
    with open('./data/metaqa_kg.pickle', 'rb') as f:
        metakg = pickle.load(f)

    print('Data loading done!!!')
    
    futures = []
    start_token = 0
    
    ####For new experiment, use it.
    result = {}
    questions_dict = {}
    entity_set_dict = {}
    label_set_dict = {}
    with open(os.path.expanduser(f"./data/onehop_test_set.jsonl")) as f:
        for line in f:
            if not line:
                continue
            q = json.loads(line)
            questions_dict[q["question_id"]] = q["question"]
            entity_set_dict[q["question_id"]] = q["entity_set"]
            label_set_dict[q["question_id"]] = q["Label"]

    # with open(f'./onehop_result.pickle', 'rb') as f:
    #     result = pickle.load(f)
    
    Correct = []
    Wrong = []
    Error = []
    Another = []

    for qid, question in questions_dict.items():
        try:                
            future = get_answer(qid, question, entity_set_dict[qid][0], KG=metakg, top_k = 3, max_tokens=1024)
            futures.append(future)
            is_correct = 0

            lower_label = []
            for lab in label_set_dict[qid]:
                if lab.lower() in future.lower():
                    is_correct += 1
                    break
            
            if is_correct > 0:
                Correct.append(qid)
                print(qid, ': Correct!')
                result[qid] = 'Correct'
            else:
                Wrong.append(qid)
                print(qid, ': Wrong...')
                result[qid] = 'Wrong'
        except Exception as e:
            print(e)
            Error.append(qid)
            print(qid, ': Error...')
            result[qid] = 'Error'
        
        with open(f'./onehop_result.pickle', 'wb') as f:
            pickle.dump(result, f)
    
    tot_corr = 0
    for tot_id in list(result):
        if result[tot_id] == 'Correct':
            tot_corr += 1
    
    print('Accuracy: ', tot_corr/len(list(result)))
