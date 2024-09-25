import re
import os
import glob
import ast
from datasets import load_dataset
import subprocess
import json
import shutil
import sys
import argparse
from transformers import AutoTokenizer
import commit0.harness.setup
from commit0.harness.constants import SPLIT, SPLIT_ALL
from commit0.harness.utils import clone_repo
from commit0.cli import write_commit0_dot_file
import pypdf
# from render_utils import _find_files_to_edit

import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

analysis_files_path = "/share/rush/commit0_analysis_temp"

def get_pytest_info(path_to_logs, repo_name, branch_name): 
    pytest_info = {}
    for pytest_hash in os.listdir(path_to_logs):
        pytest_report = json.load(open(os.path.join(path_to_logs, pytest_hash, "report.json")))
        eval_script = open(os.path.join(path_to_logs, pytest_hash, "eval.sh")).read()
        testname = re.search(r'([\S]+) > test_output', eval_script).group(1)
        patch_diff = open(os.path.join(path_to_logs, pytest_hash, "patch.diff")).read()
        pytest_info[testname] = {'hash': pytest_hash, 'patch_diff': patch_diff, 'summary': pytest_report['summary'], 'failures': {}}
        for test in pytest_report["tests"]:
            if test['outcome'] == "passed": continue
            if 'setup' in test and 'longrepr' in test['setup']:
                failure_string = test['setup']['longrepr']
            else:
                import pdb; pdb.set_trace()
            pytest_info[testname]['failures'][test['nodeid']] = failure_string
    return pytest_info

def get_coverage_info(path_to_logs, repo_name, branch_name):
    # for filename, file_coverage in json.load(open(os.path.join(path_to_logs, pytest_hash, "coverage.json")))["files"].items():
    #     if not any(relevant_function.startswith(filename) for relevant_function in relevant_functions): continue
    #     for funcname, func_coverage in file_coverage["functions"].items():
    #         if f"{filename}::{funcname}" not in relevant_functions: continue
    #         pycov_info[testname][f"{filename}::{funcname}"] = {
    #                 "implementation": submission_info["function_impls"][f"{filename}::{funcname}"],
    #                 "executed_lines": func_coverage["executed_lines"],
    #                 "executed_branches": func_coverage["executed_branches"]
    #         }
    raise NotImplementedError

def get_blank_repo_metrics(blank_source_code_folder, spec_filename, tokenizer, code_file_filter=lambda filename:filename):
    blank_repo_metrics = {
        "functions_to_edit": [],
    }
    
    for subdir, _, files in os.walk(blank_source_code_folder):
        for file in files: 
            if not code_file_filter(file): continue
            filename = os.path.join(subdir, file)
            splitted = filename.split('/')
            hidden = False
            for one in splitted:
                if one.startswith('.'):
                    hidden = True
                    break
            if hidden:
                continue
            try:
                code = open(filename, encoding='utf-8').read()
            except:
                print(f"Trouble opening {filename}")
                continue

            filename = filename[len(blank_source_code_folder):].lstrip(" /")
            try:
                code_tree = ast.parse(code)
            except:
                print(f"Trouble parsing {os.path.join(blank_source_code_folder, filename)}")
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
                        blank_repo_metrics["functions_to_edit"].append(f"{filename}::{node.parent_function}")
                    elif hasattr(node, "parent_class"): 
                        blank_repo_metrics["functions_to_edit"].append(f"{filename}::{node.parent_class}")

    # Get spec metrics
    concatted_spec = ""
    reader = pypdf.PdfReader(spec_filename)
    for p_idx, page in enumerate(reader.pages):
        try:
            concatted_spec += page.extract_text()
        except pypdf.errors.PdfReadError as e:
            print(f"Could not load page {p_idx} of {spec_filename}, excluding")
    blank_repo_metrics["no_tokens_in_spec"] = tokenizer(concatted_spec, return_tensors='pt').input_ids.shape[-1]
    
    return blank_repo_metrics

def render_mds(subfolder="docs"):
    all_submissions = {}

    method_repo_pytests = {}
    for branch_name in glob.glob(os.path.join(analysis_files_path, '*')):
        branch_name = os.path.basename(branch_name)
        if branch_name == "repos": continue
        all_submissions[branch_name] = {}
        for repo_file in glob.glob(os.path.join(analysis_files_path, branch_name, '*.json')):
            
            repo_metrics_output_file = os.path.join(analysis_files_path, branch_name, repo_file)
            print(repo_metrics_output_file)
            repo_metrics = json.load(open(repo_metrics_output_file))
            repo_name = os.path.basename(repo_file[:-len(".json")])
            
            all_submissions[branch_name][repo_name] = {}

            method_repo_pytests[f"{branch_name}_{repo_name}"] = f"# {branch_name} > {repo_name}"
            if 'pytest_results' in repo_metrics: repo_metrics = repo_metrics['pytest_results']
            for testname, pytest_info in repo_metrics.items():
                testname = os.path.basename(testname)
                all_submissions[branch_name][repo_name][testname] = pytest_info['summary']
                method_repo_pytests[f"{branch_name}_{repo_name}"] += f"""## Pytest Summary: {testname}
| status   | count |
|:---------|:-----:|
"""
                for category, count in pytest_info['summary'].items():
                    if category not in {'duration'}:
                        method_repo_pytests[f"{branch_name}_{repo_name}"] += f"""| {category} | {count} |\n"""
                    else: 
                        method_repo_pytests[f"{branch_name}_{repo_name}"] += f"""| {category} | {float(count):.2f}s |\n"""

                method_repo_pytests[f"{branch_name}_{repo_name}"] += f"\n## Failed pytest outputs: {testname}\n\n"
                for testname, failure in pytest_info['failures'].items():
                    shortened_testname = os.path.basename(testname)
                    method_repo_pytests[f"{branch_name}_{repo_name}"] += f"### {shortened_testname}\n\n<details><summary> <pre>{shortened_testname}</pre></summary><pre>\n{failure}\n</pre>\n</details>\n"

            back_button = f"[back]({os.path.join('/', f'analysis_{branch_name}')})\n\n"
            with open(os.path.join(subfolder, f"analysis_{branch_name}_{repo_name}.md"), 'w') as wf: 
                wf.write(back_button + method_repo_pytests[f"{branch_name}_{repo_name}"])    
            #     diff_info = """## Diff to gold\n"""
            #     diff_info += """<table>
            #     <thead> <th> function </th> <th data-sort-method='none'> impl </th> <th data-sort-method='none'> gold </th> <th data-sort-method='none'> diff </th> </thead>
            #     """
            #     gold_filename = f"analysis/output_metrics/{module}_gold.json"
            #     gold_experiment_metrics = json.load(open(gold_filename))
            #     import difflib
            #     d = difflib.Differ()
            #     for funcname, impl in submission_info["functions_edited"].items():
            #         if impl is None: continue
            #         impl = impl.strip("\n")
            #         gold_impl = gold_experiment_metrics["functions_edited"][funcname].strip("\n")
            #         if impl == gold_impl: continue
            #         diff = list(d.compare(impl.splitlines(), gold_impl.splitlines()))
            #         diff_info += f"""<td> <pre>{funcname}</pre> </td> 
            # <td> <pre>
            # {impl}
            # </pre> </td> 
            # <td> <pre>
            # {gold_impl}
            # </pre> </td>
            # <td> <pre>
            # {'<br>'.join(diff)}
            # </pre> </td> </tr>"""
            #     diff_info += "</table>"


    # Render general page. Has buttons to all methods
    leaderboard = """
|  | Name   |  Summary |  |
|--|--------|----------|--|"""
    # Render method page. Per method, buttons to all repos.
    method_to_repos = {}
    # Render method & repo page. Has "back" button.
    for branch_name, branch_info in all_submissions.items():
        cum_pytests = {}
        method_to_repos[branch_name] = """
| | Repository | Summary | |
|-|------------|---------|-|"""
        for repo_name, test_info in branch_info.items():
            method_to_repos[branch_name] += f"\n||[{repo_name}]({os.path.join('/', f'analysis_{branch_name}_{repo_name}')})|{str(test_info)}||"
            for category, count in test_info.items():
                if category not in cum_pytests:
                    cum_pytests[category] = 0
                if count.isdigit(): cum_pytests[category] += int(count)
                elif count.isfloat(): cum_pytests[category] += float(count)
        leaderboard += f"\n||[{branch_name}]({os.path.join('/', f'analysis_{branch_name}')})|{str(cum_pytests)}||"
        with open(os.path.join(subfolder, f"analysis_{branch_name}.md"), 'w') as wf: 
            wf.write( method_to_repos[branch_name])    
    with open(os.path.join(subfolder, "analysis.md"), 'w') as wf: 
        wf.write(leaderboard)    

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--do_setup", action="store_true")
    parser.add_argument("--get_blank_details", action="store_true")
    parser.add_argument("--get_reference_details", action="store_true")
    parser.add_argument("--keep_previous_eval", action="store_true")
    parser.add_argument("--analyze_submissions", action="store_true")
    parser.add_argument("--render_webpages", action="store_true")

    parser.add_argument("--split", type=str, default='lite')

    parser.add_argument("--tokenizer_name", type=str, default="meta-llama/Meta-Llama-3.1-8B-Instruct")

    return parser.parse_args()

def main(args):
    global analysis_files_path

    commit0_dataset_name = "wentingzhao/commit0_combined"
    submissions_dataset_name = "celinelee/commit0_submissions"
    dataset = load_dataset(commit0_dataset_name, split="test")  # type: ignore
    submission_dataset = load_dataset(submissions_dataset_name, split="train")
    

    if args.get_blank_details:
        if args.do_setup:  
            os.system(f"commit0 setup {args.split} --base-dir {analysis_files_path}/repos --commit0-dot-file-path {analysis_files_path}/repos/.commit0.yaml")
        branch_name = "blank"
        if not args.keep_previous_eval:
            if os.path.exists(os.path.join(analysis_files_path, branch_name)):
                shutil.rmtree(os.path.join(analysis_files_path, branch_name))
        os.makedirs(os.path.join(analysis_files_path, branch_name), exist_ok=True)
        # TODO use _find_files_to_edit to remove test files from src directory
        tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_name) 
        for example in dataset:
            repo_name = example["repo"].split('/')[-1]
            if args.split != "all" and repo_name not in SPLIT[args.split]:
                continue

            repo_metrics_output_file = os.path.join(analysis_files_path, branch_name, f"{repo_name}.json")
            blank_source_code_folder = os.path.join(analysis_files_path, "repos", repo_name, example["src_dir"])
            spec_filepath = os.path.join(analysis_files_path, "repos", repo_name, "spec.pdf")

            repo_metrics = get_blank_repo_metrics(
                        blank_source_code_folder, 
                        spec_filepath, 
                        tokenizer,
                        code_file_filter=lambda filename: re.fullmatch(r'.*\.py', filename) is not None, 
                    )
            json.dump(repo_metrics, open(repo_metrics_output_file, "w"), indent=4)

    if args.get_reference_details:
        if args.do_setup:  
            os.system(f"commit0 setup {args.split} --base-dir {analysis_files_path}/repos --commit0-dot-file-path {analysis_files_path}/repos/.commit0.yaml")
        branch_name = "reference"
        os.makedirs(os.path.join(analysis_files_path, branch_name), exist_ok=True)
        if not args.keep_previous_eval:
            for repo_log_path in glob.glob(f"{os.getcwd()}/logs/pytest/*"):
                if os.path.exists(os.path.join(repo_log_path, branch_name)):
                    shutil.rmtree(os.path.join(repo_log_path, branch_name))
        os.system(f"commit0 evaluate --reference --commit0-dot-file-path {analysis_files_path}/repos/.commit0.yaml")

        # get coverage and pytest info for each repo
        for example in dataset:
            repo_name = example["repo"].split('/')[-1]
            if args.split != "all" and repo_name not in SPLIT[args.split]:
                continue

            repo_metrics_output_file = os.path.join(analysis_files_path, branch_name, f"{repo_name}.json")

            path_to_logs = f"{os.getcwd()}/logs/pytest/{repo_name}/{branch_name}"
            pytest_results = get_pytest_info(path_to_logs, repo_name, branch_name)
            json.dump(pytest_results, open(repo_metrics_output_file, "w"), indent=4)

    if args.analyze_submissions:
        commit0_dot_file_path = os.path.join(analysis_files_path, "submission_repos", ".commit0.yaml")
        # if args.do_setup:  
        #     os.system(f"commit0 setup {args.split} --base-dir {analysis_files_path}/submission_repos  --commit0-dot-file-path {analysis_files_path}/submission_repos/.commit0.yaml")
        for submission in submission_dataset:
            branch_name = submission['name']
            os.makedirs(os.path.join(analysis_files_path, branch_name), exist_ok=True)
            if not args.keep_previous_eval:
                for repo_log_path in glob.glob(f"{os.getcwd()}/logs/pytest/*"):
                    if os.path.exists(os.path.join(repo_log_path, branch_name)):
                        shutil.rmtree(os.path.join(repo_log_path, branch_name))
            for example in dataset:
                repo_name = example["repo"].split('/')[-1]
                if args.split != "all" and repo_name not in SPLIT[args.split]:
                    continue
                clone_url = f"https://github.com/test-save-commit0/{repo_name}.git"
                # maybe test-save-commit0 is a submission that should be part of the dataset 
                clone_dir = os.path.abspath(os.path.join(analysis_files_path, "submission_repos", repo_name))
                repo = clone_repo(clone_url, clone_dir, branch_name, logger)
            # after successfully setup, write the commit0 dot file
            write_commit0_dot_file(
                commit0_dot_file_path,
                {
                    "dataset_name": commit0_dataset_name,
                    "dataset_split": "test",
                    "repo_split": args.split,
                    "base_dir": os.path.join(analysis_files_path, "submission_repos"),
                },
            )
            # run pytests
            os.system(f"commit0 evaluate --branch {branch_name} --commit0-dot-file-path {commit0_dot_file_path}")
            # os.system(f"commit0 get-tests {repo_name}")
            for example in dataset:
                repo_name = example["repo"].split('/')[-1]
                if args.split != "all" and repo_name not in SPLIT[args.split]:
                    continue

                repo_metrics_output_file = os.path.join(analysis_files_path, branch_name)

                path_to_logs = f"{os.getcwd()}/logs/pytest/{repo_name}/{branch_name}"
                pytest_results = get_pytest_info(path_to_logs, repo_name, branch_name)
                json.dump(pytest_results, open(repo_metrics_output_file, "w"), indent=4)
                
    if args.render_webpages: render_mds()


main(get_args())
