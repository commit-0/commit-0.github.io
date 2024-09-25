

import os
import ast
import json
import re
import glob
import argparse
from pypdf import PdfReader





def get_implementation_summary_metrics(repo_name, submission_name, repo_summary_metrics, source_code_folder, pytest_report_file, tokenizer, code_lines_filter):
    """ Collect summary metrics about a spec2repo implementation."""
    implementation_summary_metrics = {
        "module_name": repo_name,
        "submission_name": submission_name,
        "no_files_total": 0,
        "no_functions_total": 0,
        "functions_edited": {funcname: None for funcname in repo_summary_metrics["functions_to_edit"]},
        "no_lines_added": 0,
        "no_code_tokens_added": 0,
        "pytest_summary": {},
        "failed_pytests": {},
    }

    unimplemented = repo_summary_metrics["functions_to_edit"] # can have multiple fns of same name. what do?
    implementation_summary_metrics['function_edited'] = {fn: None for fn in unimplemented}
    for subdir, _, files in os.walk(source_code_folder):
        for file in files: 
            if not code_file_filter(file): continue
            filename = os.path.join(subdir, file)
            hidden = False
            for one in filename.split('/'):
                if one.startswith('.'):
                    hidden = True
                    break
            if hidden:
                continue
            implementation_summary_metrics['no_files_total'] += 1 
            try:
                code = open(filename).read()
            except:
                print(f"Trouble opening {filename}")
                continue

            filename = filename[len(source_code_folder):].lstrip(" /")

            try:
                code_tree = ast.parse(code)
            except:
                continue
            for node in ast.walk(code_tree):
                if isinstance(node, ast.ClassDef):
                    for child in node.body:
                        if isinstance(child, ast.FunctionDef):
                            child.parent_class = node.name
                if isinstance(node, ast.FunctionDef):
                    implementation_summary_metrics['no_functions_total'] += 1 # TODO see about nested functions
                    classname = ""
                    if hasattr(node, "parent_class"): 
                        classname = f"{node.parent_class}." 
                    if f"{filename}::{classname}{node.name}" in repo_summary_metrics["functions_to_edit"]:
                        # Remove comments and blank lines
                        fn_code = ast.get_source_segment(code, node)
                        if isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                            docstring = ast.get_source_segment(code, node.body[0])
                            fn_code = fn_code[fn_code.index(docstring) + len(docstring):]
                        implementation_summary_metrics["functions_edited"][f"{filename}::{classname}{node.name}"] = fn_code
                        unimplemented.remove(f"{filename}::{classname}{node.name}")
                        code_lines = [code_line for code_line in fn_code.split("\n") if code_lines_filter(code_line)]
                        implementation_summary_metrics["no_lines_added"] += len(code_lines)
                        implementation_summary_metrics["no_code_tokens_added"] += tokenizer("\n".join(code_lines), return_tensors='pt').input_ids.shape[-1]
    # if any(unimplemented):
    #     print(f"No implementation for some functions: {unimplemented}")
      
    # Get unit test metrics
    pytest_report = json.load(open(pytest_report_file))
    for category, count in pytest_report['summary'].items():
        if category in {"duration", "collected"}: continue
        implementation_summary_metrics["pytest_summary"][category] = count
    implementation_summary_metrics["pytest_summary"]["duration"] = float(pytest_report['duration'])

    for test_dict in pytest_report['tests']:
        if test_dict['outcome'] in {'xpassed', 'passed', 'xfailed', 'skipped'}: continue # TODO ask about this
        shortened_testname = test_dict['nodeid']
        if 'longrepr' in test_dict:
            implementation_summary_metrics["failed_pytests"][shortened_testname] = test_dict['longrepr']
        elif '???' in test_dict:
            implementation_summary_metrics["failed_pytests"][shortened_testname] = test_dict['???']['longrepr']
        elif test_dict['outcome'] == 'error':
            implementation_summary_metrics["failed_pytests"][shortened_testname] = test_dict['setup']['longrepr']
        elif 'call' in test_dict and 'longrepr' in test_dict['call']:
            implementation_summary_metrics["failed_pytests"][shortened_testname] = test_dict['call']['longrepr']
            # could use test_dict['call']['traceback'] information and test_dict['call']['crash'] for more info
        else: import pdb; pdb.set_trace()

    return implementation_summary_metrics

# os.makedirs(os.path.join("analysis", "output_metrics"), exist_ok=True)

# output_file = os.path.join("analysis", "output_metrics", f"{args.repo_name}_{args.submission_name}.json")
# # if os.path.exists(output_file): 
# #     stop = input(f"{output_file} exits. Overwrite? (y/)").strip() != "y"
# #     if stop: exit(0)

# tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_name) 
# code_file_filter = lambda filename: re.fullmatch(args.code_file_regex, filename) is not None
# code_line_filter = lambda code_line: re.fullmatch(args.code_line_regex, code_line) is not None
# spec_file_filter = lambda filename: re.fullmatch(args.spec_file_regex, filename) is not None
# empty_repo_metrics_output_file = os.path.join("analysis", "repo_metrics", f"{args.repo_name}.json")
# if os.path.exists(empty_repo_metrics_output_file):
#     blank_repo_metrics = json.load(open(empty_repo_metrics_output_file))
#     # print(f"Loaded blank repo metrics from {empty_repo_metrics_output_file}")
# else:
#     assert args.blank_source_code_folder is not None, f"Need to provide blank source code repo path because info DNE"
#     assert args.spec_folder is not None, f"Need to provide blank specs path because info DNE"

#     os.makedirs(os.path.join("analysis", "repo_metrics"), exist_ok=True)
#     blank_repo_metrics = get_blank_repo_metrics(args.blank_source_code_folder, code_file_filter, args.to_impl_text, args.spec_folder, spec_file_filter, tokenizer)
#     json.dump(blank_repo_metrics, open(empty_repo_metrics_output_file, "w"), indent=4)
#     # print(f"Saved blank repo metrics to {empty_repo_metrics_output_file}")

# submission_metrics = get_implementation_summary_metrics(
#     args.repo_name,
#     args.submission_name,
#     blank_repo_metrics, 
#     args.submission_source_code_folder,
#     args.pytest_report_file,
#     tokenizer,
#     code_lines_filter=code_line_filter
# )

# json.dump(submission_metrics, open(output_file, 'w'), indent=4)
# # print(f"Saved {args.submission_name} impl of {args.repo_name} to {output_file}")

# ## NOW GENERATE MKDOCS PAGES
# repo_pages_to_update = []
# for submission_file in glob.glob("analysis/output_metrics/*.json"):
#     submission_info = json.load(open(submission_file))
#     try:
#         module = submission_info["module_name"]
#         method = submission_info["submission_name"]
#     except: continue
#     # print(submission_file)

#     repo_pages_to_update.append((f"{module}_{method}", os.path.join("/", f"analysis_{module}", method), submission_file))

# repo_selection_button = "# Select repository\n" + \
#                         "\n\n".join(f"[{submitted_repo}]({webpage}){{ .md-button }}" for submitted_repo, webpage, _ in repo_pages_to_update)
# with open(f"docs/analysis.md", "w") as wf:
#     wf.write(repo_selection_button + "\n\n## Summary \n\n## Pytest outputs\n\n## Diff to gold")

# for (_, webpage, submission_file) in repo_pages_to_update:
#     if (f"{args.repo_name}/{args.submission_name}" not in webpage) and os.path.exists(f"docs/{webpage}.md"):
#         existing_doc = open(f"docs/{webpage}.md").read()
#         to_write = repo_selection_button + "\n\n" + existing_doc.split("{ .md-button }")[-1].strip()
#         with open(f"docs/{webpage}.md", "w") as wf:
#             wf.write(to_write)
#         continue

#     submission_info = json.load(open(submission_file))
#     module = submission_info["module_name"]
#     method = submission_info["submission_name"]

#     summary_info = f"""## Implementation Summary {module}::{method}
# | metric | value |
# |:---|:---:|
# | no. lines gen | {submission_info['no_lines_added']} |
# | no. code toks gen | {submission_info['no_code_tokens_added']} |
# """
#     for category, count in submission_info['pytest_summary'].items():
#         if category not in {'duration'}:
#             summary_info += f"""| {category} | {count} |\n"""
#         else: 
#             summary_info += f"""| {category} | {float(submission_info['pytest_summary'][category]):.2f}s |\n"""

#     pytest_info = """## Failed pytest outputs\n\n"""
#     for testname, failure in submission_info['failed_pytests'].items():
#         shortened_testname = os.path.basename(testname)
#         pytest_info += f"### {shortened_testname}\n\n<details><summary> <pre>{shortened_testname}</pre></summary><pre>\n{failure}\n</pre>\n</details>\n"

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

#     if not os.path.exists(os.path.dirname(f"docs/{webpage}.md")):
#         os.makedirs(os.path.dirname(f"docs/{webpage}.md"), exist_ok=True)
#     with open(f"docs/{webpage}.md", "w") as wf:
#         wf.write(repo_selection_button + "\n\n" + summary_info + "\n\n" + pytest_info + "\n\n" + diff_info)

