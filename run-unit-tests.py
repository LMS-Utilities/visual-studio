# Written by Andrew Haselgrove and Benjamin Luke Saljooghi

import csv
import logging
import os
import re
import tempfile
import shutil
import subprocess
import sys
from pathlib import Path
import multiprocessing
import time
from dataclasses import dataclass
from typing import List
import coloredlogs
from subprocess import PIPE




def get_path(path: Path, search: str):
    if path.name == search:
        # print(path)
        return path
    if path.is_dir():
        for d in path.iterdir():
            result = get_path(d, search)
            if result:
                return result            

# path = Path("CAB402GeneticAlgorithm")
# result = get_dir(path, "GAUnitTests")
# print(result)


# quit()




# --------- PYPARAMS ------------

coloredlogs.install(level="DEBUG")
logging.basicConfig(format = "%(asctime)s | %(levelname)s | %(message)s", level="DEBUG")

# ----------- PARAMS ------------

TARGET = Path('gradebook').absolute()
PROJECT = 'CAB402GeneticAlgorithm'
SOLUTION = 'CAB402GeneticAlgorithm.sln'
# CUSTOM_CODE = ['ScheduleModel', 'GeneticAlgorithm']
CUSTOM_CODE = ['CSharpSchedule']
TIMEOUT = 60 * 60 * 1000 # ms
CORES = 12
OVERWRITES = [
    # Path("CAB402StudyPlanner", "FSharpModel", "BoundsOptimizer.fs")
] 
STUDENT_RESTRICTION = []

# https://docs.microsoft.com/en-us/dotnet/core/testing/selective-unit-tests
TARGETS = [
    ("GAUnitTests/GAUnitTests.csproj", "CrossAtTests", "ClassName=GeneticAlgorithmUnitTests.CrossAtTests"),
    ("GAUnitTests/GAUnitTests.csproj", "CrossTests", "ClassName=GeneticAlgorithmUnitTests.CrossTests"),
    ("GAUnitTests/GAUnitTests.csproj", "ElitismSelectionTests", "ClassName=GeneticAlgorithmUnitTests.ElitismSelectionTests"),
    ("GAUnitTests/GAUnitTests.csproj", "EvolveForeverTests", "ClassName=GeneticAlgorithmUnitTests.EvolveForeverTests"),
    ("GAUnitTests/GAUnitTests.csproj", "EvolveOneGenerationTests", "ClassName=GeneticAlgorithmUnitTests.EvolveOneGenerationTests"),
    ("GAUnitTests/GAUnitTests.csproj", "FitestTests", "ClassName=GeneticAlgorithmUnitTests.FitestTests"),
    ("GAUnitTests/GAUnitTests.csproj", "PossiblyMutateTests", "ClassName=GeneticAlgorithmUnitTests.PossiblyMutateTests"),
    ("GAUnitTests/GAUnitTests.csproj", "ProcreateTests", "ClassName=GeneticAlgorithmUnitTests.ProcreateTests"),
    ("GAUnitTests/GAUnitTests.csproj", "RandomIndividualsTests", "ClassName=GeneticAlgorithmUnitTests.RandomIndividualsTests"),
    ("GAUnitTests/GAUnitTests.csproj", "ReverseMutateAtTests", "ClassName=GeneticAlgorithmUnitTests.ReverseMutateAtTests"),
    ("GAUnitTests/GAUnitTests.csproj", "ReverseMutateTests", "ClassName=GeneticAlgorithmUnitTests.ReverseMutateTests"),
    ("GAUnitTests/GAUnitTests.csproj", "ScoreTests", "ClassName=GeneticAlgorithmUnitTests.ScoreTests"),
    ("GAUnitTests/GAUnitTests.csproj", "TournamentSelectTests", "ClassName=GeneticAlgorithmUnitTests.TournamentSelectTests"),
    ("GAUnitTests/GAUnitTests.csproj", "TournamentWinnerTests", "ClassName=GeneticAlgorithmUnitTests.TournamentWinnerTests"),
    ("ScheduleUnitTests/ScheduleUnitTests.csproj", "AthleticsScheduleCostTests", "ClassName=ScheduleUnitTests.AthleticsScheduleCostTests"),
    ("ScheduleUnitTests/ScheduleUnitTests.csproj", "EarliestStartTests", "ClassName=ScheduleUnitTests.EarliestStartTests"),
    ("ScheduleUnitTests/ScheduleUnitTests.csproj", "ScheduleNextTests", "ClassName=ScheduleUnitTests.ScheduleNextTests"),
    ("ScheduleUnitTests/ScheduleUnitTests.csproj", "ScheduleTests", "ClassName=ScheduleUnitTests.ScheduleTests"),
]

RESULTS = 'results.csv'

# ----------- IMPLEMENTATION ------------
@dataclass
class Test:
    path: str
    name: str
    target: str

    def to_cmd(self, temp_dir, ):
        return ["dotnet", "test", os.path.join(temp_dir, PROJECT, self.path), "--filter", self.target, "-c", "Release", "--", f"RunConfiguration.TestSessionTimeout={TIMEOUT}", f"RunConfiguration.MaxCpuCount={CORES}"]

TESTS = [Test(*args) for args in TARGETS]
logging.info("targets built")
# FIELDNAMES = ['studentno'] + ['{}_{}'.format(test.name, field) for test in TESTS for field in ['Passed', 'Time']]
# print(FIELDNAMES)

def prepare_project():
    temp_dir = tempfile.mkdtemp()
    logging.debug(f"Created temporary directory {temp_dir}")
    project_dir = os.path.join(temp_dir, PROJECT)
    shutil.copytree(PROJECT, project_dir)
    return temp_dir


def cleanup_project(temp_dir):
    logging.debug("cleaning up temporary directory")
    shutil.rmtree(temp_dir)


def read_results():
    logging.debug(f"reading results from {RESULTS}")
    try:
        with open(RESULTS, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            return {row['studentno']: row for row in reader}
        
    except IOError:
        # File doesn't exist - there are no existing results
        return None


def write_results(test_results):

    field_names = list(list(test_results.values())[0].keys())

    logging.debug(f"writing results to {RESULTS}")
    try:
        with open(RESULTS, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=field_names)
            writer.writeheader()
            for _, row in sorted(test_results.items()):
                writer.writerow(row)
    
    except IOError:
        # File can't be written - writing to stdout
        writer = csv.DictWriter(sys.stdout, fieldnames=field_names)
        writer.writeheader()
        for _, row in sorted(test_results.items()):
            writer.writerow(row)


def apply_common_copy_logic(temp_dir, student_dir, student_no):
    try:
        for code_dir in CUSTOM_CODE:
            removal = os.path.join(temp_dir, PROJECT, code_dir)
            logging.debug(f"removing {removal}")
            shutil.rmtree(removal)

            # source = os.path.join(TARGET, student_dir, PROJECT, code_dir)
            source = get_path(Path(TARGET, student_dir), code_dir)
            if not source:                    
                logging.error(f"failed to find in {student_dir}: {code_dir}")
            
            logging.debug(f"copying {source} -> {removal}")
            shutil.copytree(source, removal)
        
        for overwrite in OVERWRITES:
            _src = overwrite
            _des = Path(temp_dir, PROJECT, overwrite.parent.name, overwrite.name)
            logging.debug(f"cpy {_src} -> {_des}")
            shutil.copy(overwrite, _des)


    except Exception as e:
        logging.error("something went wrong during copying of student files, skipping tests")
        logging.error(f"{str(e)}")
        logging.error(f"{student_no}")
        raise e


def run_all_tests(temp_dir, existing_results=None):
    existing_results = existing_results or {}
    logging.debug(f"running against restricted students {STUDENT_RESTRICTION}")
    for student_dir in TARGET.iterdir():
        student_no = student_dir
        if STUDENT_RESTRICTION and student_no not in STUDENT_RESTRICTION:
            logging.debug(f"skipping student {student_no} - not restricted")
            continue
        if student_no in existing_results:
            logging.debug(f"skipping student {student_no} - already tested")
            continue
        logging.debug(f"testing student {student_no}")
        test_results = run_tests(student_no, temp_dir, student_dir)
        existing_results[student_no] = test_results
        write_results(existing_results)



def run_specific_console(temp_dir, existing_results=None):
    existing_results = existing_results or {}
    logging.debug(f"running specific console")


    SPECIFIC_CONSOLE_PROJECT_PATH = "CSTester"

    for student_dir in TARGET.iterdir():
        student_no = student_dir.name
        test_results = {'studentno': student_no}
        if student_no in existing_results:
            logging.debug(f"skipping student {student_no} - already tested")
            continue
            
        logging.debug(f"testing student {student_no}")
        apply_common_copy_logic(temp_dir, student_dir, student_no)
        cmd = ["dotnet", "run", "--configuration", "Release", "--project", Path(temp_dir, PROJECT, SPECIFIC_CONSOLE_PROJECT_PATH)]
        logging.debug(f"running {cmd}")
        process = subprocess.run(cmd, stdout=PIPE, stderr=PIPE)
        stdout_run = process.stdout.decode("utf-8")
        stderr_run = process.stderr.decode("utf-8")
        logging.info(stdout_run)
        logging.warning(stderr_run)

        seconds = float(re.search("Total time elapsed: (.*) seconds", stdout_run).groups()[0])
        search = re.search("Best tour after (.*) iterations without improvement: (.*)", stdout_run)

        iterations = int(search.groups()[0])
        shortest_tour = float(search.groups()[1])

        test_results[f"seconds"] = str(seconds)
        test_results[f"shortest tour"] = str(shortest_tour)

        existing_results[student_no] = test_results
        write_results(existing_results)

def run_tests(student_no, temp_dir, student_dir):

    apply_common_copy_logic(temp_dir, student_dir, student_no)

    # Run tests
    test_results = {'studentno': student_no}

    stdout_build = ""
    stderr_build = ""
    stdout_run = ""
    stderr_run = ""
    try:
        for test in TESTS:
            logging.debug(f"testing {test.name}")
            

            cmd = test.to_cmd(temp_dir)
            logging.debug(f"running {cmd}")
            process_test = subprocess.run(cmd, stdout=PIPE, stderr=PIPE)            
            stdout_run = process_test.stdout.decode("utf-8")
            stderr_run = process_test.stderr.decode("utf-8")

            if f"test run timeout of {TIMEOUT} milliseconds exceeded" in stderr_run:
                logging.debug(f"timeout encountered for {test.name}")
                test_results[f"{test.name}_Passed"] = "TIMEOUT"
                # test_results[f"{test.name}_Time"] = "TIMEOUT"
                continue
                
            ms_attempt = re.search("Duration: (.*) ms", stdout_run)
            s_attempt = re.search("Duration: (.*) s", stdout_run)

            total_s = 0
            if ms_attempt:
                total_s = float(ms_attempt.groups()[0]) / float(1000)
            if s_attempt:
                total_s = float(s_attempt.groups()[0])

            def funcy(ting):
                return int(re.search(f"{ting}:[ \t]+([0-9]+)", stdout_run).groups()[0])
            
            count_failed = funcy("Failed")
            count_passed = funcy("Passed")
            count_skipped = funcy("Skipped")
            count_total = funcy("Total")

            if count_skipped > 0:
                logging.debug(f"ALERT ALERT ALERT ALERT ALERT ALERT ALERT ALERT")

            assert(count_failed + count_passed == count_total)

            test_results[f"{test.name}_Passed"] = count_passed
            test_results[f"{test.name}_Time"] = total_s
            logging.debug(f"tests complete. passed: {count_passed}, time: {total_s} s")
    

    except Exception as e:
        logging.error(f"something went during testing: {e}")
        logging.error(f"diagnostics: {stdout_run=} {stderr_run=}")
        logging.error(f"{student_no}")
        # raise e
    

    return test_results


def compile_check():
    for student_dir in Path(TARGET).iterdir():
        result = get_path(student_dir, "CAB402GeneticAlgorithm.sln")

        if not result:
            logging.error(f"student did not have an sln {student_dir}")
            continue

        for d in result.parent.iterdir():
            if d.is_dir() and d.name in CUSTOM_CODE:
                # logging.debug(f"compiling {d}")
                process_test = subprocess.run(["dotnet", "build"], stdout=PIPE, stderr=PIPE, cwd=d)            
                stdout_run = process_test.stdout.decode("utf-8")
                stderr_run = process_test.stderr.decode("utf-8")

                # logging.debug(stdout_run)

                if "Build succeeded" in stdout_run:
                    logging.debug(f"compiled {student_dir.name}")
                else:
                    logging.error(f"failure on {student_dir}")
                    logging.error(stdout_run)                 
                    logging.error(stderr_run)

def main():
    try:
        temp_dir = prepare_project()
        existing_results = read_results()
        # run_all_tests(temp_dir, existing_results)
        run_specific_console(temp_dir, existing_results)
    except KeyboardInterrupt:
        logging.debug('keyboard interrupt received -> gracefully exiting...')
    cleanup_project(temp_dir)


if __name__ == '__main__':
    main()
