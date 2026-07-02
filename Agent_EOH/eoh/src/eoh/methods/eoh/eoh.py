import numpy as np
import json
import random
import time
import hashlib
from pathlib import Path

from .eoh_interface_EC import InterfaceEC


def _code_hash(code):
    if not isinstance(code, str):
        return None
    return hashlib.sha1(code.encode("utf-8", errors="replace")).hexdigest()[:12]


def _offspring_audit_entry(operator, index, offspring):
    if not isinstance(offspring, dict):
        offspring = {}
    code = offspring.get("code")
    return {
        "operator": operator,
        "index": index,
        "objective": offspring.get("objective"),
        "has_code": isinstance(code, str) and bool(code.strip()),
        "code_hash": _code_hash(code),
        "code": code,
        "algorithm": offspring.get("algorithm"),
        "other_inf": offspring.get("other_inf"),
    }


def _is_raw_valid(entry):
    try:
        objective = float(entry.get("objective"))
    except Exception:
        return False
    return entry.get("has_code") and objective < 1e8


def _objective_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _offspring_audit_summary(entries, survivor_population):
    code_hashes = {
        entry.get("code_hash")
        for entry in entries
        if entry.get("code_hash")
    }
    objectives = [
        entry.get("objective")
        for entry in entries
        if entry.get("objective") is not None
    ]
    unique_objectives = []
    for objective in objectives:
        if objective not in unique_objectives:
            unique_objectives.append(objective)
    survivor_objectives = [
        item.get("objective")
        for item in survivor_population
        if isinstance(item, dict)
    ]
    raw_valid = sum(1 for entry in entries if _is_raw_valid(entry))
    final_size = len(survivor_population)
    if raw_valid >= 5 and final_size < 5:
        survivor_drop_reason = "objective_or_code_dedup"
    elif raw_valid < 5:
        survivor_drop_reason = "raw_generation_or_evaluation_shortfall"
    else:
        survivor_drop_reason = "survivor_population_ok"
    return {
        "raw_offspring_count": len(entries),
        "raw_with_code_count": sum(1 for entry in entries if entry.get("has_code")),
        "raw_penalty_count": sum(
            1
            for entry in entries
            if _objective_float(entry.get("objective")) is None
            or not entry.get("has_code")
            or _objective_float(entry.get("objective")) >= 1e8
        ),
        "raw_valid_candidate_count": raw_valid,
        "unique_code_count": len(code_hashes),
        "unique_objective_count": len(unique_objectives),
        "survivor_population_size": final_size,
        "survivor_objectives": survivor_objectives,
        "survivor_drop_reason": survivor_drop_reason,
    }


def _write_json(path, payload):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=5)


# main class for eoh
class EOH:

    # initilization
    def __init__(self, paras, problem, select, manage, **kwargs):

        self.prob = problem
        self.select = select
        self.manage = manage
        
        # LLM settings
        self.use_local_llm = paras.llm_use_local
        self.llm_local_url = paras.llm_local_url
        self.api_endpoint = paras.llm_api_endpoint  # currently only API2D + GPT
        self.api_key = paras.llm_api_key
        self.llm_model = paras.llm_model

        # ------------------ RZ: use local LLM ------------------
        # self.use_local_llm = kwargs.get('use_local_llm', False)
        # assert isinstance(self.use_local_llm, bool)
        # if self.use_local_llm:
        #     assert 'url' in kwargs, 'The keyword "url" should be provided when use_local_llm is True.'
        #     assert isinstance(kwargs.get('url'), str)
        #     self.url = kwargs.get('url')
        # -------------------------------------------------------

        # Experimental settings       
        self.pop_size = paras.ec_pop_size  # popopulation size, i.e., the number of algorithms in population
        self.n_pop = paras.ec_n_pop  # number of populations

        self.operators = paras.ec_operators
        self.operator_weights = paras.ec_operator_weights
        if paras.ec_m > self.pop_size or paras.ec_m == 1:
            print("m should not be larger than pop size or smaller than 2, adjust it to m=2")
            paras.ec_m = 2
        self.m = paras.ec_m

        self.debug_mode = paras.exp_debug_mode  # if debug
        self.ndelay = 1  # default

        self.use_seed = paras.exp_use_seed
        self.seed_path = paras.exp_seed_path
        self.load_pop = paras.exp_use_continue
        self.load_pop_path = paras.exp_continue_path
        self.load_pop_id = paras.exp_continue_id

        self.output_path = paras.exp_output_path

        self.exp_n_proc = paras.exp_n_proc
        
        self.timeout = paras.eva_timeout

        self.use_numba = paras.eva_numba_decorator

        print("- EoH parameters loaded -")

        # Set a random seed
        random.seed(2024)

    # add new individual to population
    def add2pop(self, population, offspring):
        for off in offspring:
            for ind in population:
                if ind['objective'] == off['objective']:
                    if (self.debug_mode):
                        print("duplicated result, retrying ... ")
            population.append(off)
    

    # run eoh 
    def run(self):

        print("- Evolution Start -")

        time_start = time.time()

        # interface for large language model (llm)
        # interface_llm = PromptLLMs(self.api_endpoint,self.api_key,self.llm_model,self.debug_mode)

        # interface for evaluation
        interface_prob = self.prob

        # interface for ec operators
        interface_ec = InterfaceEC(self.pop_size, self.m, self.api_endpoint, self.api_key, self.llm_model, self.use_local_llm, self.llm_local_url,
                                   self.debug_mode, interface_prob, select=self.select,n_p=self.exp_n_proc,
                                   timeout = self.timeout, use_numba=self.use_numba
                                   )

        # initialization
        population = []
        if self.use_seed:
            with open(self.seed_path, "rb") as file:
                raw = file.read()
            data = None
            for enc in ["utf-8", "utf-8-sig", "gbk", "latin-1"]:
                try:
                    data = json.loads(raw.decode(enc))
                    break
                except Exception:
                    continue
            if data is None:
                raise ValueError(f"failed to decode seed file: {self.seed_path}")
            population = interface_ec.population_generation_seed(data,self.exp_n_proc)
            filename = self.output_path + "/results/pops/population_generation_0.json"
            with open(filename, 'w') as f:
                json.dump(population, f, indent=5)
            n_start = 0
        else:
            if self.load_pop:  # load population from files
                print("load initial population from " + self.load_pop_path)
                with open(self.load_pop_path) as file:
                    data = json.load(file)
                for individual in data:
                    population.append(individual)
                print("initial population has been loaded!")
                n_start = self.load_pop_id
            else:  # create new population
                print("creating initial population:")
                population = interface_ec.population_generation()
                population = self.manage.population_management(population, self.pop_size)

                # print(len(population))
                # if len(population)<self.pop_size:
                #     for op in [self.operators[0],self.operators[2]]:
                #         _,new_ind = interface_ec.get_algorithm(population, op)
                #         self.add2pop(population, new_ind)
                #         population = self.manage.population_management(population, self.pop_size)
                #         if len(population) >= self.pop_size:
                #             break
                #         print(len(population))
     
                
                print(f"Pop initial: ")
                for off in population:
                    print(" Obj: ", off['objective'], end="|")
                print()
                print("initial population has been created!")
                # Save population to a file
                filename = self.output_path + "/results/pops/population_generation_0.json"
                with open(filename, 'w') as f:
                    json.dump(population, f, indent=5)
                n_start = 0

        # main loop
        n_op = len(self.operators)

        for pop in range(n_start, self.n_pop):  
            generation_offspring_entries = []
            #print(f" [{na + 1} / {self.pop_size}] ", end="|")         
            for i in range(n_op):
                op = self.operators[i]
                print(f" OP: {op}, [{i + 1} / {n_op}] ", end="|") 
                op_w = self.operator_weights[i]
                parents, offsprings = [], []
                if (np.random.rand() < op_w):
                    parents, offsprings = interface_ec.get_algorithm(population, op)
                operator_entries = [
                    _offspring_audit_entry(op, index, off)
                    for index, off in enumerate(offsprings)
                ]
                generation_offspring_entries.extend(operator_entries)
                _write_json(
                    self.output_path + "/results/offsprings/pop_" + str(pop + 1) + "_" + op + ".json",
                    operator_entries,
                )
                self.add2pop(population, offsprings)  # Check duplication, and add the new offspring
                for off in offsprings:
                    print(" Obj: ", off['objective'], end="|")
                # if is_add:
                #     data = {}
                #     for i in range(len(parents)):
                #         data[f"parent{i + 1}"] = parents[i]
                #     data["offspring"] = offspring
                #     with open(self.output_path + "/results/history/pop_" + str(pop + 1) + "_" + str(
                #             na) + "_" + op + ".json", "w") as file:
                #         json.dump(data, file, indent=5)
                # populatin management
                size_act = min(len(population), self.pop_size)
                population = self.manage.population_management(population, size_act)
                print()


            # Save population to a file
            filename = self.output_path + "/results/pops/population_generation_" + str(pop + 1) + ".json"
            with open(filename, 'w') as f:
                json.dump(population, f, indent=5)

            audit_summary = _offspring_audit_summary(generation_offspring_entries, population)
            _write_json(
                self.output_path + "/results/offsprings/offspring_audit_generation_" + str(pop + 1) + ".json",
                audit_summary,
            )

            # Save the best one to a file
            filename = self.output_path + "/results/pops_best/population_generation_" + str(pop + 1) + ".json"
            with open(filename, 'w') as f:
                json.dump(population[0], f, indent=5)


            print(f"--- {pop + 1} of {self.n_pop} populations finished. Time Cost:  {((time.time()-time_start)/60):.1f} m")
            print("Pop Objs: ", end=" ")
            for i in range(len(population)):
                print(str(population[i]['objective']) + " ", end="")
            print()
