import argparse
import json
import os
import re
import sys
import time
from typing import Any, Dict

import requests

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import react_tools_insertships as react_tools


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)
            s.flush()

    def flush(self):
        for s in self.streams:
            s.flush()


class AutonomousEoHAgent:
    def __init__(self, api_key, api_endpoint="https://api.deepseek.com", model="deepseek-v4-pro", name="Agent"):
        self.api_key = api_key
        self.api_endpoint = api_endpoint
        self.model = model
        self.name = name
        self.tools = {
            "run_evolution": react_tools.run_evolution,
            "analyze_latest_results": react_tools.analyze_latest_results,
            "web_search": react_tools.web_search,
            "generate_seeds_from_research": react_tools.generate_seeds_from_research,
            "read_research_notes": react_tools.read_research_notes,
            "read_plan": react_tools.read_plan,
            "update_plan": react_tools.update_plan,
            "read_memory": react_tools.read_memory,
            "update_memory": react_tools.update_memory,
            "run_deep_analysis": react_tools.run_deep_analysis,
            "run_code_review": react_tools.run_code_review,
            "add_new_seed": react_tools.add_new_seed,
            "run_comprehensive_evaluation": react_tools.run_comprehensive_evaluation,
            "write_report": react_tools.write_report,
            "finish": react_tools.finish,
        }

    def _get_tool_descriptions(self):
        return "\n".join(
            [
                f"- {name}: {func.__doc__.strip() if func.__doc__ else 'No description available.'}"
                for name, func in self.tools.items()
            ]
        )

    def _get_skills_from_file(self):
        skills_path = os.path.join(os.path.dirname(__file__), "SKILLS.md")
        if os.path.exists(skills_path):
            with open(skills_path, "r", encoding="utf-8") as f:
                return f.read()
        return "Tool Descriptions:\n" + self._get_tool_descriptions()

    def run(self, high_level_goal: str, max_loops=6):
        print(f"=== Starting Autonomous Agent ({self.name}) with Goal: '{high_level_goal}' ===")
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        force_fallback = os.environ.get("EOH_FORCE_FALLBACK", "0") == "1"

        system_prompt = f"""
You are an Autonomous AI Research Scientist specializing in Evolutionary Heuristics (EoH).
Your primary mission is: {high_level_goal}

Problem: Implement a Go function:
func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch

You must output JSON only, in the required format.

### 🧠 Autonomous Goal Setting & Strategy
- Self-Discovery: If your goal is broad (e.g., "improve performance"), your FIRST priority should be to use read_plan and read_memory to see current targets and constraints. Then use read_research_notes to reuse existing knowledge. If not enough, use web_search.
- Knowledge Extraction: If you find promising operator ideas during web_search or read_research_notes, your NEXT step should be to convert them into concrete seeds:
  - Use generate_seeds_from_research to create a research seed file, and/or
  - Use add_new_seed to append a new Go InsertShips candidate.
  - CRITICAL: The code for add_new_seed MUST be a complete Go method definition `func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch { ... }`. Do not include package/imports.
- Quality Control: Before using add_new_seed, you MUST call run_code_review to ensure the method compiles and passes a smoke run.
- Error Awareness: If you observe many penalty objectives or stagnation at baseline, use analyze_latest_results and run_deep_analysis, then update_plan/update_memory with actionable changes.
- Final Verification: After evolution, use run_comprehensive_evaluation and write_report to compare against Archive_extracted/final_result.txt baseline.

### 🔄 ReAct Framework (Thought -> Action -> Observation)
1. Thought: Reason about the current situation.
   - Always read PLAN.md and MEMORY.md first and keep them updated.
2. Action: Choose ONE tool.
3. Observation: Analyze the tool's output and update PLAN.md/MEMORY.md after major steps.

Available Tools:
{self._get_skills_from_file()}

Your response MUST be in this EXACT JSON format:
{{
  "thought": "...",
  "action": {{
    "tool_name": "name_of_the_tool_to_use",
    "args": {{ "arg1": "value1" }}
  }}
}}
"""

        history = []
        for i in range(max_loops):
            print(f"\n--- Loop {i+1}/{max_loops} ---")
            prompt = system_prompt
            if history:
                recent_history = history[-10:] if len(history) > 10 else history
                prompt += "\n\n--- Recent History ---\n" + "\n".join(recent_history)

            llm_response = None if force_fallback else self._call_llm(prompt)
            if not llm_response:
                fallback = self._fallback_action(loop_index=i, high_level_goal=high_level_goal)
                thought = fallback.get("thought")
                action = fallback.get("action")
            else:
                thought = llm_response.get("thought")
                action = llm_response.get("action")

            if not thought or not action:
                history.append("Observation: Invalid JSON format. Please correct it.")
                continue

            print(f"Thought: {thought}")
            history.append(f"Thought: {thought}")

            tool_name = action.get("tool_name")
            args = action.get("args", {})
            history.append(f"Action: {json.dumps(action)}")

            if tool_name in self.tools:
                try:
                    result = self.tools[tool_name](**args)
                except BaseException as e:
                    result = f"Error executing tool {tool_name}: {e}"

                print(f"Observation: {result}")
                history.append(f"Observation: {result}")

                if tool_name == "finish":
                    print("\n=== Agent has finished the task. ===")
                    break
            else:
                history.append(f"Observation: The tool '{tool_name}' does not exist.")

    def _extract_goal_int(self, text: str, key: str, default: int) -> int:
        m = re.search(rf"{re.escape(key)}\s*=\s*(\d+)", text or "")
        if not m:
            return int(default)
        return int(m.group(1))

    def _fallback_action(self, loop_index: int, high_level_goal: str) -> Dict[Any, Any]:
        if loop_index == 0:
            return {
                "thought": "LLM unavailable, executing fallback run_evolution.",
                "action": {
                    "tool_name": "run_evolution",
                    "args": {
                        "generations": self._extract_goal_int(high_level_goal, "generations", 1),
                        "sim_time_multi": self._extract_goal_int(high_level_goal, "sim_time_multi", 10),
                        "max_instances": self._extract_goal_int(high_level_goal, "max_instances", 1),
                        "pop_size": self._extract_goal_int(high_level_goal, "pop_size", 4),
                        "run_timeout_s": self._extract_goal_int(high_level_goal, "run_timeout_s", 60),
                        "eva_timeout": self._extract_goal_int(high_level_goal, "eva_timeout", 120),
                    },
                },
            }
        if loop_index == 1:
            return {
                "thought": "LLM unavailable, executing fallback analyze_latest_results.",
                "action": {"tool_name": "analyze_latest_results", "args": {}},
            }
        return {
            "thought": "LLM unavailable, executing fallback finish.",
            "action": {"tool_name": "finish", "args": {}},
        }

    def _call_llm(self, prompt: str) -> Dict[Any, Any] | None:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
        }

        endpoint = self.api_endpoint
        if not endpoint.startswith("http"):
            endpoint = f"https://{endpoint}"

        try:
            response = requests.post(f"{endpoint}/v1/chat/completions", json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            resp_json = response.json()

            usage = resp_json.get("usage", {})
            self.total_prompt_tokens += usage.get("prompt_tokens", 0)
            self.total_completion_tokens += usage.get("completion_tokens", 0)

            response_str = resp_json["choices"][0]["message"]["content"]
            return json.loads(response_str)
        except Exception:
            return None


def _normalize_endpoint(raw_endpoint: str) -> str:
    endpoint = (raw_endpoint or "api.deepseek.com").strip().strip('"').strip("`").strip()
    endpoint = endpoint.rstrip("/")
    endpoint = re.sub(r"/v1/chat/completions$", "", endpoint)
    if endpoint.startswith("http://"):
        endpoint = endpoint.replace("http://", "https://", 1)
    if not endpoint.startswith("http"):
        endpoint = f"https://{endpoint}"
    return endpoint


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-loops", type=int, default=6)
    parser.add_argument("--goal", type=str, default="")
    parser.add_argument("--log-file", type=str, default="")
    args = parser.parse_args()

    config = react_tools.load_config()
    deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY") or config.get("deepseek_api_key", "")
    deepseek_api_endpoint = os.environ.get("DEEPSEEK_API_ENDPOINT") or config.get("deepseek_api_endpoint", "api.deepseek.com")
    llm_model = os.environ.get("DEEPSEEK_MODEL") or config.get("llm_model", "deepseek-v4-pro")
    if not deepseek_api_key:
        print("Warning: No DeepSeek API key found.")

    if args.log_file:
        log_path = os.path.abspath(args.log_file)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        log_f = open(log_path, "w", encoding="utf-8")
        sys.stdout = Tee(sys.stdout, log_f)
        sys.stderr = Tee(sys.stderr, log_f)
        print(f"=== Logging to: {log_path} ===")
        print(f"=== Start time: {time.strftime('%Y-%m-%d %H:%M:%S')} ===")

    agent = AutonomousEoHAgent(
        api_key=deepseek_api_key,
        api_endpoint=_normalize_endpoint(deepseek_api_endpoint),
        model=llm_model,
    )
    goal = args.goal.strip() or "Run evolution for 1 generation with max_instances=1, then analyze_latest_results, then finish."
    agent.run(high_level_goal=goal, max_loops=int(args.max_loops))

    if args.log_file:
        print(f"=== End time: {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
