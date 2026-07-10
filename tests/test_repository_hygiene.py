from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
Q3_MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "eoh_rag_workspace"
    / "experiments"
    / "manifests"
    / "bp_ablation_cards_q3.json"
)
CANDIDATE_REGISTRY_PATH = REPOSITORY_ROOT / "eoh_rag_workspace" / "candidate_registry.json"
Q3_HELD_OUT_DIRECTORY = (
    REPOSITORY_ROOT / "eoh_rag_workspace" / "problems" / "bp_online" / "held_out"
)
EXECUTABLE_SUFFIXES = {".py", ".sh", ".ps1", ".bat", ".cmd"}
# 拆开字面量，避免卫生测试把用于检测的规则本身误判为绝对路径。
ABSOLUTE_USER_PATH_MARKERS = ("/" + "Users/", "C:" + "\\Users\\")


def _is_runtime_text_file(path: Path) -> bool:
    """判断文件是否会影响实际运行，避免把冻结证据中的历史路径当成当前配置。"""

    relative_path = path.relative_to(REPOSITORY_ROOT)

    # 冻结证据需要保留来源机器路径才能审计；迁移文档也需要记录旧路径来解释清理原因。
    if relative_path.parts[0] == "evidence":
        return False
    if relative_path.parts[:2] == ("docs", "migrations"):
        return False

    if path.suffix.lower() in EXECUTABLE_SUFFIXES:
        return True

    manifest_root = Path("eoh_rag_workspace", "experiments", "manifests")
    try:
        relative_path.relative_to(manifest_root)
    except ValueError:
        return False
    return path.is_file()


class RepositoryHygieneTests(unittest.TestCase):
    def test_runtime_code_and_manifests_do_not_use_user_absolute_paths(self) -> None:
        violations: list[str] = []

        for path in REPOSITORY_ROOT.rglob("*"):
            if not path.is_file() or not _is_runtime_text_file(path):
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            for marker in ABSOLUTE_USER_PATH_MARKERS:
                if marker in content:
                    relative_path = path.relative_to(REPOSITORY_ROOT).as_posix()
                    violations.append(f"{relative_path}: contains {marker!r}")

        self.assertEqual([], violations, "发现依赖本机用户目录的可执行文件或 manifest")

    def test_q3_manifest_exists_and_is_valid_json(self) -> None:
        self.assertTrue(Q3_MANIFEST_PATH.is_file(), f"缺少 Q3 manifest: {Q3_MANIFEST_PATH}")

        # 除了存在性，还要保证清理过程中没有留下无法解析的半成品配置。
        manifest = json.loads(Q3_MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(manifest, dict)

    def test_obsolete_candidate_registry_is_removed(self) -> None:
        self.assertFalse(
            CANDIDATE_REGISTRY_PATH.exists(),
            "旧注册表只包含失效的本机绝对路径，不应继续保留在版本库中",
        )

    def test_q3_held_out_pickle_files_are_not_tracked(self) -> None:
        held_out_pathspec = Q3_HELD_OUT_DIRECTORY.relative_to(REPOSITORY_ROOT).as_posix()
        result = subprocess.run(
            ["git", "ls-files", "--", held_out_pathspec],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        tracked_pickle_files = [
            line for line in result.stdout.splitlines() if Path(line).suffix.lower() == ".pkl"
        ]

        self.assertEqual(
            [],
            tracked_pickle_files,
            "Q3 使用的 HiFo held-out pickle 属于外部原始数据，只能由准备脚本下载或导入",
        )


if __name__ == "__main__":
    unittest.main()
