from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import traceback
import warnings

from prompts_insertships_go import GetPrompts


def _find_upwards_dir(start_dir: str, target_dir_name: str, max_depth: int = 10) -> str | None:
    cur = os.path.abspath(start_dir)
    for _ in range(max_depth):
        candidate = os.path.join(cur, target_dir_name)
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def _find_upwards_project_root(start_dir: str, max_depth: int = 12) -> str | None:
    cur = os.path.abspath(start_dir)
    for _ in range(max_depth):
        if os.path.isfile(os.path.join(cur, "main.go")) and os.path.isfile(os.path.join(cur, "routing.go")):
            return cur
        # Go 求解器单独放在 go_solver/ 子目录时,从该子目录定位
        go_solver = os.path.join(cur, "go_solver")
        if os.path.isfile(os.path.join(go_solver, "main.go")) and os.path.isfile(os.path.join(go_solver, "routing.go")):
            return go_solver
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def _parse_final_cost(output: str) -> float | None:
    m = re.search(r"final cost\s+(-?\d+(?:\.\d+)?)", output)
    if not m:
        m = re.search(r"final\s+cost\s*[:=]\s*(-?\d+(?:\.\d+)?)", output, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"total\s+cost\s*[:=]\s*(-?\d+(?:\.\d+)?)", output, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def _parse_res_time(output: str) -> float | None:
    m = re.search(r"RES\s+(-?\d+(?:\.\d+)?)", output)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def _target_function() -> str:
    return os.environ.get("EOH_TARGET_FUNCTION", "InsertShips").strip() or "InsertShips"


def _target_regex(target_function: str) -> str:
    if target_function == "Optimization":
        return r"func\s+Optimization\s*\(\s*dispatch\s+Dispatch\s*,\s*temperature\s+float64\s*\)\s*Dispatch\s*\{[\s\S]*?\n\}"
    return r"func\s+InsertShips\s*\(\s*dispatch\s+Dispatch\s*,\s*oris\s*,\s*dess\s*\[\]Station\s*,\s*total_ship\s+int\s*\)\s*Dispatch\s*\{[\s\S]*?\n\}"


def _replace_target_method(main_go_path: str, new_method: str, target_function: str | None = None) -> None:
    target_function = target_function or _target_function()
    with open(main_go_path, "r", encoding="utf-8") as f:
        s = f.read()
    pat = _target_regex(target_function)
    m = re.search(pat, s)
    if not m:
        raise ValueError(f"{target_function} method not found in main.go")
    s2 = s[: m.start()] + new_method.strip() + "\n" + s[m.end() :]
    if "sort." in new_method:
        s2 = _ensure_go_import(s2, "sort")
    if "SortManager" in new_method and not re.search(r"type\s+SortManager\s+struct\s*\{", s2):
        s2 = _inject_sort_manager_definition(s2, target_function)
    with open(main_go_path, "w", encoding="utf-8") as f:
        f.write(s2)


def _ensure_go_import(go_text: str, pkg_name: str) -> str:
    import_block = re.search(r"import\s*\(([^)]*)\)", go_text, flags=re.DOTALL)
    if not import_block:
        return go_text
    body = import_block.group(1)
    if re.search(rf'^\s*"{re.escape(pkg_name)}"\s*$', body, flags=re.MULTILINE):
        return go_text
    updated_body = body.rstrip() + f'\n    "{pkg_name}"\n'
    return go_text[: import_block.start(1)] + updated_body + go_text[import_block.end(1) :]


def _inject_sort_manager_definition(go_text: str, target_function: str = "InsertShips") -> str:
    insert_pos = go_text.find(f"func {target_function}(")
    if insert_pos < 0:
        return go_text
    sort_manager_block = (
        "type SortManager struct {\n"
        "    inds []int\n"
        "    values []float64\n"
        "}\n\n"
        "func (sm *SortManager) Len() int {\n"
        "    return len(sm.inds)\n"
        "}\n\n"
        "func (sm *SortManager) Swap(i, j int) {\n"
        "    sm.inds[i], sm.inds[j] = sm.inds[j], sm.inds[i]\n"
        "}\n\n"
        "func (sm *SortManager) Less(i, j int) bool {\n"
        "    return sm.values[sm.inds[i]] < sm.values[sm.inds[j]]\n"
        "}\n\n"
    )
    return go_text[:insert_pos] + sort_manager_block + go_text[insert_pos:]

def _safe_write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _kill_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


# 允许透传给子进程（go build / 运行求解器）的环境变量白名单。
# 只保留 Go 工具链和临时目录所需的变量，避免把无关或敏感的环境变量（如 API 密钥）带入子进程。
_SUBPROCESS_ENV_ALLOWLIST = {
    "PATH",
    "HOME",
    "TMPDIR",
    "TEMP",
    "TMP",
    "GOCACHE",
    "GOPATH",
    "GOMODCACHE",
    "LOCALAPPDATA",
    "USERPROFILE",
}


def _safe_subprocess_env() -> dict[str, str]:
    """构造传给子进程的最小环境变量集合。

    仅保留白名单 _SUBPROCESS_ENV_ALLOWLIST 中列出的变量，其余一律过滤掉，
    使被编译/执行的候选代码无法读取 API 密钥等敏感环境变量。
    """
    return {key: value for key, value in os.environ.items() if key in _SUBPROCESS_ENV_ALLOWLIST}


def _run_command(cmd: list[str], cwd: str, timeout_s: int) -> dict:
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
        env=_safe_subprocess_env(),  # 使用白名单环境变量，隔离外部环境
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        return {
            "returncode": proc.returncode,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "timeout": False,
        }
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc.pid)
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except Exception:
            stdout, stderr = "", ""
        return {
            "returncode": None,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "timeout": True,
        }


class Evaluation:
    def __init__(
        self,
        sim_time_multi: int = 10,
        max_instances: int = 1,
        per_instance_penalty: float = 1e9,
        build_timeout_s: int = 60,
        run_timeout_s: int = 15,
        dataset_density: str = "d100",
        sim_time_interval: int = 1,
        arrival_scale: float = 1.0,
        use_density_source_dirs: bool = False,
    ):
        self.prompts = GetPrompts()
        self._last_error = None
        self._last_traceback = None

        base_dir = os.path.dirname(__file__)
        archive_dir = _find_upwards_dir(base_dir, "Archive_extracted", max_depth=12)
        if archive_dir is None:
            archive_dir = _find_upwards_project_root(base_dir, max_depth=12)
        if archive_dir is None:
            archive_dir = os.path.abspath(os.path.join(base_dir, "..", "..", "..", "..", "..", ".."))
        self.archive_dir = os.path.abspath(archive_dir)

        self.dataset_density = dataset_density
        self.use_density_source_dirs = bool(use_density_source_dirs)
        self._using_density_source_dir = False
        self.solomon_dir = self._resolve_solomon_dir()
        self.sim_time_multi = int(sim_time_multi)
        self.max_instances = int(max_instances)
        self.per_instance_penalty = float(per_instance_penalty)
        self.build_timeout_s = int(build_timeout_s)
        self.run_timeout_s = int(run_timeout_s)
        self.sim_time_interval = int(sim_time_interval)
        self.arrival_scale = float(arrival_scale)
        env_arrival_scale = os.environ.get("EOH_ARRIVAL_SCALE")
        if env_arrival_scale:
            try:
                self.arrival_scale = float(env_arrival_scale)
            except Exception:
                pass
        env_use_density_source_dirs = os.environ.get("EOH_USE_DENSITY_SOURCE_DIRS")
        if env_use_density_source_dirs:
            self.use_density_source_dirs = env_use_density_source_dirs.strip().lower() in ("1", "true", "yes", "on")
            self.solomon_dir = self._resolve_solomon_dir()
        env_timeout = os.environ.get("EOH_RUN_TIMEOUT_S")
        if env_timeout:
            try:
                self.run_timeout_s = int(env_timeout)
            except Exception:
                pass

        self.objective_use_composite = os.environ.get("EOH_OBJECTIVE_USE_COMPOSITE", "0") == "1"
        try:
            self.objective_res_weight = float(os.environ.get("EOH_RES_WEIGHT", "0.0"))
        except Exception:
            self.objective_res_weight = 0.0

        all_files = sorted([f for f in os.listdir(self.solomon_dir) if f.lower().endswith(".json")])
        self.instance_files = [os.path.join(self.solomon_dir, f) for f in all_files[: self.max_instances]]

        self.go_main = os.path.join(self.archive_dir, "main.go")
        self.go_routing = os.path.join(self.archive_dir, "routing.go")
        self.go_mod = os.path.join(self.archive_dir, "go.mod")
        self.go_sum = os.path.join(self.archive_dir, "go.sum")

    def _resolve_solomon_dir(self) -> str:
        default_dir = os.path.join(self.archive_dir, "solomon_benchmark")
        self._using_density_source_dir = False
        if self.use_density_source_dirs:
            density = str(self.dataset_density).lower().strip()
            density_dir = os.path.join(self.archive_dir, f"solomon_benchmark_{density}")
            if os.path.isdir(density_dir):
                self._using_density_source_dir = True
                return density_dir
        return default_dir

    def _density_pct(self) -> float:
        if self._using_density_source_dir:
            return 1.0
        d = self.dataset_density.lower().strip()
        m = re.match(r"d(\d+)", d)
        if m:
            return int(m.group(1)) / 100.0
        return 1.0

    def _prepare_filtered_json(self, src_path: str, dst_dir: str) -> str:
        with open(src_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        changed = False
        for be in data.get("batch", []):
            for key in ("ori", "des"):
                arr = be.get(key, [])
                if arr:
                    n = len(arr)
                    keep = max(1, int(n * self._density_pct()))
                    if keep < n:
                        be[key] = arr[:keep]
                        changed = True
            if self.sim_time_interval > 1:
                for key in ("ori", "des"):
                    for item in be.get(key, []):
                        old = item.get("timeEnd", 0)
                        item["timeEnd"] = max(1, int(old / self.sim_time_interval))
                        changed = True
            if abs(self.arrival_scale - 1.0) > 1e-9 and "timeReady" in be:
                old_ready = be.get("timeReady", 0)
                try:
                    new_ready = max(0, int(round(float(old_ready) * self.arrival_scale)))
                except Exception:
                    new_ready = old_ready
                if new_ready != old_ready:
                    be["timeReady"] = new_ready
                    changed = True
        if not changed:
            return src_path
        dst = os.path.join(dst_dir, os.path.basename(src_path))
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return dst

    def _build_and_run(self, target_method_go: str) -> float | None:
        tmp = tempfile.mkdtemp(prefix="eoh_insertships_go_")
        try:
            shutil.copy2(self.go_main, os.path.join(tmp, "main.go"))
            shutil.copy2(self.go_routing, os.path.join(tmp, "routing.go"))
            shutil.copy2(self.go_mod, os.path.join(tmp, "go.mod"))
            if os.path.exists(self.go_sum):
                shutil.copy2(self.go_sum, os.path.join(tmp, "go.sum"))

            main_go_path = os.path.join(tmp, "main.go")
            _replace_target_method(main_go_path, target_method_go, self.prompts.get_func_name())

            build = _run_command(
                ["go", "build", "-o", "mainbin.exe", "."],
                cwd=tmp,
                timeout_s=self.build_timeout_s,
            )
            if build["returncode"] != 0:
                self._last_error = "Go build failed"
                self._last_traceback = json.dumps(
                    [
                        {
                            "stage": "build",
                            "returncode": build["returncode"],
                            "timeout": build["timeout"],
                            "stdout": build["stdout"],
                            "stderr": build["stderr"],
                        }
                    ],
                    ensure_ascii=False,
                )
                return None

            import concurrent.futures
            filtered_instance_files = [
                self._prepare_filtered_json(ip, tmp) for ip in self.instance_files
            ]
            total = 0.0
            details = []
            
            def _run_single_instance(inst_path: str) -> dict:
                run = _run_command(
                    [os.path.join(tmp, "mainbin.exe"), inst_path, str(self.sim_time_multi)],
                    cwd=tmp,
                    timeout_s=self.run_timeout_s,
                )
                out = (run["stdout"] or "") + "\n" + (run["stderr"] or "")
                cost = _parse_final_cost(out)
                res_time = _parse_res_time(out)
                name = os.path.basename(inst_path)
                return {
                    "instance": name,
                    "cost": cost,
                    "res": res_time,
                    "returncode": run["returncode"],
                    "timeout": run["timeout"],
                    "stdout": run["stdout"],
                    "stderr": run["stderr"],
                }

            with concurrent.futures.ThreadPoolExecutor() as executor:
                results = list(executor.map(_run_single_instance, filtered_instance_files))
                
            for res in results:
                details.append(res)
                if res["cost"] is None or res["cost"] < 0:
                    total += self.per_instance_penalty
                else:
                    obj = float(res["cost"])
                    if self.objective_use_composite and res.get("res") is not None and res["res"] >= 0:
                        obj += self.objective_res_weight * float(res["res"])
                    total += obj
            self._last_traceback = json.dumps(details, ensure_ascii=False)
            if all((item.get("cost") is None or item.get("cost") < 0) for item in details):
                detail_lines = []
                for item in details:
                    stdout_preview = (item.get("stdout") or "")[:400]
                    stderr_preview = (item.get("stderr") or "")[:400]
                    detail_lines.append(
                        f"instance={item.get('instance')} rc={item.get('returncode')} cost={item.get('cost')} stdout={stdout_preview!r} stderr={stderr_preview!r}"
                    )
                self._last_error = "All instances failed to produce valid cost"
                self._last_traceback = "\n".join(detail_lines)
            return total / max(len(self.instance_files), 1)
        finally:
            try:
                shutil.rmtree(tmp, ignore_errors=True)
            except Exception:
                pass

    def evaluate(self, code_string):
        self._last_error = None
        self._last_traceback = None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")

                target_name = self.prompts.get_func_name()
                if "func" not in code_string or target_name not in code_string:
                    self._last_error = f"Missing {target_name} method definition"
                    return self.per_instance_penalty

                fitness = self._build_and_run(code_string)
                if fitness is None:
                    return self.per_instance_penalty
                return float(fitness)
        except Exception as e:
            self._last_error = f"General error: {str(e)}"
            self._last_traceback = json.dumps(
                [
                    {
                        "stage": "evaluate",
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    }
                ],
                ensure_ascii=False,
            )
            return self.per_instance_penalty
