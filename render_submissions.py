import re
import os
import glob
import ast
import subprocess
import json
import shutil
import argparse
import pypdf
import tqdm

from datasets import load_dataset
from transformers import AutoTokenizer

from commit0.harness.constants import SPLIT
from commit0.harness.utils import clone_repo
from commit0.cli import write_commit0_dot_file

import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

analysis_files_path = "/share/rush/commit0_analysis_temp"


def get_pytest_info(path_to_logs, repo_name, branch_name):
    pytest_info = {}
    for pytest_hash in os.listdir(path_to_logs):
        eval_script = open(os.path.join(path_to_logs, pytest_hash, "eval.sh")).read()
        testname = re.search(r"([\S]+) > test_output", eval_script).group(1)
        patch_diff = open(os.path.join(path_to_logs, pytest_hash, "patch.diff")).read()
        pytest_info[testname] = {
            "hash": pytest_hash,
            "patch_diff": patch_diff,
            "failures": {},
        }
        report_file_path = os.path.join(path_to_logs, pytest_hash, "report.json")
        if not os.path.exists(report_file_path):
            if os.path.exists(os.path.join(path_to_logs, pytest_hash, "test_output.txt")):
                reason_for_failure = open(
                    os.path.join(path_to_logs, pytest_hash, "test_output.txt")
                ).read()
            else: 
                reason_for_failure = "Unknown failure."
            pytest_info[testname]["failed_to_run"] = reason_for_failure
            return pytest_info
        pytest_report = json.load(open(report_file_path))
        pytest_summary = pytest_report["summary"]
        pytest_info[testname]["summary"] = pytest_summary
        # TODO this is a hacky fix, should eventually do a check against true num collected
        if pytest_summary["collected"] < 5:
            reason_for_failure = "Pytest collection failure."
            pytest_info[testname]["failed_to_run"] = reason_for_failure
            return pytest_info
        pytest_info[testname]["duration"] = pytest_report["duration"]
        if "passed" not in pytest_summary:
            pytest_summary["passed"] = 0
        for test in pytest_report["tests"]:
            if test["outcome"] == "passed":
                continue
            if "longrepr" in test:
                failure_string = test["longrepr"]
            elif "???" in test:
                failure_string = test["???"]["longrepr"]
            elif test["outcome"] == "error":
                failure_string = test["setup"]["longrepr"]
            elif "setup" in test and "longrepr" in test["setup"]:
                failure_string = test["setup"]["longrepr"]
            elif "call" in test and "longrepr" in test["call"]:
                failure_string = test["call"]["longrepr"]
                # could use test['call']['traceback'] information and test['call']['crash'] for more info
            else:
                failure_string = ""
            duration = 0.0
            for action_key in ["setup", "call", "teardown"]:
                if action_key not in test:
                    continue
                if "duration" in test:
                    duration += test["duration"]
            pytest_info[testname]["failures"][test["nodeid"]] = {
                "failure_string": failure_string,
                "duration": duration,
            }
    return pytest_info


def get_coverage_info(path_to_logs, repo_name, branch_name):
    raise NotImplementedError


def get_blank_repo_metrics(
    blank_source_code_folder,
    spec_filename,
    tokenizer,
    code_file_filter=lambda filename: filename,
):
    blank_repo_metrics = {
        "functions_to_edit": [],
    }

    for subdir, _, files in os.walk(blank_source_code_folder):
        for file in files:
            if not code_file_filter(file):
                continue
            filename = os.path.join(subdir, file)
            splitted = filename.split("/")
            hidden = False
            for one in splitted:
                if one.startswith("."):
                    hidden = True
                    break
            if hidden:
                continue
            try:
                code = open(filename, encoding="utf-8").read()
            except Exception as e:
                print(f"{e}: Trouble opening {filename}")
                continue

            filename = filename[len(blank_source_code_folder) :].lstrip(" /")
            try:
                code_tree = ast.parse(code)
            except Exception as e:
                print(
                    f"{e}: Trouble parsing {os.path.join(blank_source_code_folder, filename)}"
                )
                continue
            for node in ast.walk(code_tree):
                if isinstance(node, ast.ClassDef):
                    for child in node.body:
                        child.parent_class = node.name
                elif isinstance(node, ast.FunctionDef) and len(node.body) > 0:
                    classname = ""
                    if hasattr(node, "parent_class"):
                        classname = f"{node.parent_class}."
                    for child in node.body:
                        child.parent_function = f"{classname}{node.name}"
                elif isinstance(node, ast.Pass):
                    if hasattr(node, "parent_function"):
                        blank_repo_metrics["functions_to_edit"].append(
                            f"{filename}::{node.parent_function}"
                        )
                    elif hasattr(node, "parent_class"):
                        blank_repo_metrics["functions_to_edit"].append(
                            f"{filename}::{node.parent_class}"
                        )

    # Get spec metrics
    concatted_spec = ""
    reader = pypdf.PdfReader(spec_filename)
    for p_idx, page in enumerate(reader.pages):
        try:
            concatted_spec += page.extract_text()
        except pypdf.errors.PdfReadError as e:
            print(f"{e}: Could not load page {p_idx} of {spec_filename}, excluding...")
    blank_repo_metrics["no_tokens_in_spec"] = tokenizer(
        concatted_spec, return_tensors="pt"
    ).input_ids.shape[-1]

    return blank_repo_metrics


def render_mds(subfolder="docs"):
    leaderboard = {}

    for split in tqdm.tqdm(["lite", "all"]):
        num_repos = len(SPLIT[split])
        leaderboard[
            split
        ] = f"""\n\n## Leaderboard ({split})
| Name | Repos Resolved (/{num_repos}) | Test Duration (s) | Date | Analysis | Github | 
|------|:-------------------------:|:--------------------:|:----------:|----|----| """

    for org_path in tqdm.tqdm(glob.glob(os.path.join(analysis_files_path, "*"))):
        org_name = os.path.basename(org_path)
        if org_name in {"blank", "repos", "submission_repos"}:
            continue
        repos_resolved = 0
        # cum_passed = 0
        total_duration = 0.0
        for branch_path in glob.glob(os.path.join(org_path, "*.json")):
            branch_metrics = json.load(open(branch_path))
            submission_info = branch_metrics["submission_info"]
            split = submission_info["split"]
            org_name = submission_info["org_name"]
            project_page_link = submission_info["project_page"]
            display_name = submission_info["display_name"]
            submission_date = submission_info["submission_date"]
            branch_name = submission_info["branch"]
            submission_page = f"""# Submission Name: **{display_name}** (split: {split})

| Repository | Resolved | Pass Rate | Test Duration (s) | Analysis | Github Link |
|------------|---------|:-----:|:-----:|-----|-----|"""

            for repo_name, repo_pytest_results in branch_metrics.items():
                if repo_name == "submission_info": continue
                submission_repo_page = (
                    f"# **{display_name}**: {repo_name}"
                )
                for pytest_group, pytest_info in repo_pytest_results.items():
                    pytest_group = os.path.basename(pytest_group.strip("/"))
                    patch_diff = (
                        f"""\n\n## Patch diff\n```diff\n{pytest_info['patch_diff']}```"""
                    )
                    if "failed_to_run" in pytest_info:
                        submission_repo_page += f"""\n## Failed to run pytests for test `{pytest_group}`\n```\n{pytest_info['failed_to_run']}\n```"""
                        resolved = False
                        pytest_details = "Pytest failed"
                        duration = "Failed."
                    else:
                        submission_repo_page += f"""\n## Pytest Summary for test `{pytest_group}`
| status   | count |
|:---------|:-----:|
"""
                        total_duration += pytest_info["duration"]
                        # cum_passed += pytest_info["summary"]["passed"]
                        for category, count in pytest_info["summary"].items():
                            if category not in {"duration"}:
                                submission_repo_page += f"""| {category} | {count} |\n"""
                            else:
                                submission_repo_page += (
                                    f"""| {category} | {float(count):.2f}s |\n"""
                                )

                        submission_repo_page += "\n## Failed pytests:\n\n"
                        for testname, failure in pytest_info["failures"].items():
                            shortened_testname = os.path.basename(testname)
                            submission_repo_page += (
                                f"### {shortened_testname}\n\n<details><summary> <pre>{shortened_testname}"
                                f"</pre></summary><pre>\n{failure['failure_string']}\n</pre>\n</details>\n"
                            )
                        resolved = ("failed" not in pytest_info["summary"]) or (
                            pytest_info["summary"]["failed"] == 0
                        )
                        repos_resolved += int(resolved)
                        pytest_details = f"{pytest_info['summary']['passed']} / {pytest_info['summary']['collected']}"
                        duration = f"{pytest_info['duration']:.2f}"
                github_hyperlink = f"{project_page_link}/{repo_name}" if branch_name == "reference" else f"{project_page_link}/{repo_name}/tree/{branch_name}"
                submission_page += f"""
| {repo_name} | {'Yes' if resolved else 'No'} | {pytest_details} | {duration} | [Analysis](/{f'analysis_{org_name}_{branch_name}_{repo_name}'}) | [Github]({github_hyperlink}) |"""
                back_button = (
                    f"[back to {display_name} summary](/{f'analysis_{org_name}_{branch_name}'})\n\n"
                )
                with open(
                    os.path.join(subfolder, f"analysis_{org_name}_{branch_name}_{repo_name}.md"), "w"
                ) as wf:
                    wf.write(back_button + submission_repo_page + patch_diff)
        analysis_link = f"[Analysis](/{f'analysis_{org_name}_{branch_name}'})"
        github_link = f"[Github]({project_page_link})"
        leaderboard[split] += (
            f"\n|{display_name}|"
            f"{repos_resolved}|"
            f"{total_duration:.2f}|"
            f"{submission_date}|"
            f"{analysis_link}|"
            f"{github_link}|"
        )

        back_button = f"[back to all submissions](/{f'analysis'})\n\n"
        with open(os.path.join(subfolder, f"analysis_{org_name}_{branch_name}.md"), "w") as wf:
            wf.write(back_button + "\n" + submission_page)

    with open(os.path.join(subfolder, "analysis.md"), "w") as wf:
        wf.write(leaderboard["lite"] + leaderboard["all"])


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--do_setup", action="store_true")
    parser.add_argument("--get_blank_details", action="store_true")
    parser.add_argument("--get_reference_details", action="store_true")
    parser.add_argument("--keep_previous_eval", action="store_true")
    parser.add_argument("--analyze_submissions", action="store_true")
    parser.add_argument("--render_webpages", action="store_true")

    parser.add_argument("--split", type=str, default="lite")

    parser.add_argument(
        "--tokenizer_name", type=str, default="meta-llama/Meta-Llama-3.1-8B-Instruct"
    )

    return parser.parse_args()


def main(args):
    global analysis_files_path

    commit0_dataset_name = "wentingzhao/commit0_combined"
    submissions_dataset_name = "celinelee/commit0_submissions"
    dataset = load_dataset(commit0_dataset_name, split="test")  # type: ignore
    submission_dataset = load_dataset(submissions_dataset_name, split="train")

    if args.get_blank_details:
        if args.do_setup:
            os.system(
                f"commit0 setup {args.split} --base-dir {analysis_files_path}/repos "
                f"--commit0-dot-file-path {analysis_files_path}/repos/.commit0.yaml"
            )
        branch_name = "blank"
        if not args.keep_previous_eval:
            if os.path.exists(os.path.join(analysis_files_path, branch_name)):
                shutil.rmtree(os.path.join(analysis_files_path, branch_name))
        os.makedirs(os.path.join(analysis_files_path, branch_name), exist_ok=True)
        tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_name)
        for example in dataset:
            repo_name = example["repo"].split("/")[-1]
            if args.split != "all" and repo_name not in SPLIT[args.split]:
                continue

            repo_metrics_output_file = os.path.join(
                analysis_files_path, branch_name, f"{repo_name}.json"
            )
            blank_source_code_folder = os.path.join(
                analysis_files_path, "repos", repo_name, example["src_dir"]
            )
            spec_filepath = os.path.join(
                analysis_files_path, "repos", repo_name, "spec.pdf"
            )

            repo_metrics = get_blank_repo_metrics(
                blank_source_code_folder,
                spec_filepath,
                tokenizer,
                code_file_filter=lambda filename: re.fullmatch(r".*\.py", filename)
                is not None,
            )
            json.dump(repo_metrics, open(repo_metrics_output_file, "w"), indent=4)

    if args.get_reference_details:
        if args.do_setup:
            os.system(
                f"commit0 setup {args.split} --base-dir {analysis_files_path}/repos "
                f"--commit0-dot-file-path {analysis_files_path}/repos/.commit0.yaml"
            )
        branch_name = "reference"
        org_name = "commit0"
        submission_metrics_output_file = os.path.join(
            analysis_files_path, org_name, f"{branch_name}.json"
        )
        submission_details = {"submission_info": {
            "org_name": org_name,
            "branch": branch_name,
            "display_name": "Reference (Gold)",
            "submission_date": "NA",
            "split": args.split,
            "project_page": "https://github.com/commit-0",
        }}

        os.makedirs(os.path.join(analysis_files_path, org_name), exist_ok=True)
        if not args.keep_previous_eval:
            for repo_log_path in glob.glob(f"{os.getcwd()}/logs/pytest/*"):
                if os.path.exists(os.path.join(repo_log_path, branch_name)):
                    shutil.rmtree(os.path.join(repo_log_path, branch_name))
        os.system(
            "commit0 evaluate --reference "
            f"--commit0-dot-file-path {analysis_files_path}/repos/.commit0.yaml"
        )
        # get coverage and pytest info for each repo
        for example in dataset:
            repo_name = example["repo"].split("/")[-1]
            if args.split != "all" and repo_name not in SPLIT[args.split]:
                continue

            path_to_logs = f"{os.getcwd()}/logs/pytest/{repo_name}/{branch_name}"
            pytest_results = get_pytest_info(path_to_logs, repo_name, branch_name)
            submission_details[repo_name] = pytest_results
        json.dump(submission_details, open(submission_metrics_output_file, "w"), indent=4)
        print(f"Saved pytest info to {submission_metrics_output_file}")

    if args.analyze_submissions:
        if not args.keep_previous_eval:
            for subfolder in glob.glob(os.path.join(analysis_files_path, "*")):
                if os.path.basename(subfolder.rstrip("/")) not in {
                    "blank",
                    "repos",
                    "submission_repos",
                    "commit0"
                }:
                    try:
                        print(f"Clearing {subfolder}")
                        shutil.rmtree(subfolder)
                    except Exception as e:
                        print(f"{e}: when removing {subfolder}")

        for submission in tqdm.tqdm(submission_dataset):
            submission_details = {"submission_info": submission}
            branch_name = submission["branch"]
            org_name = submission["org_name"]
            submission_metrics_output_file = os.path.join(
                analysis_files_path, org_name, f"{branch_name}.json"
            )
            os.makedirs(os.path.join(analysis_files_path, org_name), exist_ok=True)
            commit0_dot_file_path = os.path.join(
                analysis_files_path, "submission_repos", org_name, ".commit0.yaml"
            )
            print("commit0_dot_file_path", commit0_dot_file_path)
            if not args.keep_previous_eval:
                for repo_log_path in glob.glob(f"{os.getcwd()}/logs/pytest/*"):
                    if os.path.exists(os.path.join(repo_log_path, branch_name)):
                        shutil.rmtree(os.path.join(repo_log_path, branch_name))
            for example in dataset:
                repo_name = example["repo"].split("/")[-1]
                if args.split != "all" and repo_name not in SPLIT[args.split]:
                    continue
                clone_url = f"https://github.com/{org_name}/{repo_name}.git"
                clone_dir = os.path.abspath(
                    os.path.join(analysis_files_path, "submission_repos", org_name, repo_name)
                )
                clone_repo(clone_url, clone_dir, branch_name, logger)
            # after successfully setup, write the commit0 dot file
            write_commit0_dot_file(
                commit0_dot_file_path,
                {
                    "dataset_name": commit0_dataset_name,
                    "dataset_split": "test",
                    "repo_split": args.split,
                    "base_dir": os.path.join(analysis_files_path, "submission_repos", org_name),
                },
            )
            # run pytests
            os.system(
                f"commit0 evaluate --branch {branch_name} "
                f"--commit0-dot-file-path {commit0_dot_file_path}"
            )
            for example in dataset:
                repo_name = example["repo"].split("/")[-1]
                if args.split != "all" and repo_name not in SPLIT[args.split]:
                    continue

                path_to_logs = f"{os.getcwd()}/logs/pytest/{repo_name}/{branch_name}"
                pytest_results = get_pytest_info(path_to_logs, repo_name, branch_name)
                submission_details[repo_name] = pytest_results
            json.dump(submission_details, open(submission_metrics_output_file, "w"), indent=4)
            print(f"Saved pytest info to {submission_metrics_output_file}")
            break

    if not args.keep_previous_eval:
        for analysis_file in glob.glob("docs/analysis*.md"):
            os.unlink(analysis_file)
    if args.render_webpages:
        render_mds()


main(get_args())
