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



# --------- PYPARAMS ------------

coloredlogs.install(level="DEBUG")
logging.basicConfig(format = "%(asctime)s | %(levelname)s | %(message)s", level="DEBUG")

# ----------- PARAMS ------------

TARGET = Path('phase-1').absolute().__str__()
PROJECT = 'CAB402StudyPlanner'
SOLUTION = 'CAB402StudyPlanner.sln'
CUSTOM_CODE = ['CSharpModel', 'FSharpModel']
TESTS_PROJ = "ModelUnitTests\\ModelUnitTests.csproj" 
TIMEOUT = 60 * 60 * 1000 # ms
CORES = 80
OVERWRITES = [
    # Path("CAB402StudyPlanner", "FSharpModel", "BoundsOptimizer.fs")
] 
STUDENT_RESTRICTION = []
TARGETS = {     # https://docs.microsoft.com/en-us/dotnet/core/testing/selective-unit-tests
    "CSharpTryToImproveScheduleTests": "ClassName=ModelUnitTests.CSharpTryToImproveScheduleTests",
    "FSharpTryToImproveScheduleTests": "ClassName=ModelUnitTests.FSharpTryToImproveScheduleTests",
    "UnitPrereqsTests": "ClassName=ModelUnitTests.UnitPrereqsTests",
    "boundUnitsInPlanTests": "ClassName=ModelUnitTests.boundUnitsInPlanTests",
    "displayOfferedTests": "ClassName=ModelUnitTests.displayOfferedTests",
    "displayTests": "ClassName=ModelUnitTests.displayTests",
    "getPrereqTests": "ClassName=ModelUnitTests.getPrereqTests",
    "getUnitTitleTests": "ClassName=ModelUnitTests.getUnitTitleTests",
    "isEnrollableInTests": "ClassName=ModelUnitTests.isEnrollableInTests",
    "isEnrollableTests": "ClassName=ModelUnitTests.isEnrollableTests",
    "isLegalInTests": "ClassName=ModelUnitTests.isLegalInTests",
    "isLegalPlanTests": "ClassName=ModelUnitTests.isLegalPlanTests",
    "unitDependenciesWithinPlanTests": "ClassName=ModelUnitTests.unitDependenciesWithinPlanTests"
}


RESULTS = 'results.csv'


# ----------- IMPLEMENTATION ------------



@dataclass
class Test:
    name: str
    path: str
    target: str

    def to_cmd(self, temp_dir, ):
        return ["dotnet", "test", os.path.join(temp_dir, PROJECT, self.path), "--filter", self.target, "-c", "Release", "--", f"RunConfiguration.TestSessionTimeout={TIMEOUT}", f"RunConfiguration.MaxCpuCount={CORES}"]

TESTS = [Test(name, TESTS_PROJ, target) for name, target in TARGETS.items()]
logging.info("targets built")
FIELDNAMES = ['studentno'] + ['{}_{}'.format(test.name, field) for test in TESTS for field in ['Passed']]

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
    logging.debug(f"writing results to {RESULTS}")
    try:
        with open(RESULTS, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
            writer.writeheader()
            for _, row in sorted(test_results.items()):
                writer.writerow(row)
    
    except IOError:
        # File can't be written - writing to stdout
        writer = csv.DictWriter(sys.stdout, fieldnames=FIELDNAMES)
        writer.writeheader()
        for _, row in sorted(test_results.items()):
            writer.writerow(row)


def run_all_tests(temp_dir, existing_results=None):
    existing_results = existing_results or {}
    try:
        
        logging.debug(f"running against restricted students {STUDENT_RESTRICTION}")

        for student_dir in os.listdir(TARGET):
            student_no = student_dir

            if STUDENT_RESTRICTION and student_no not in STUDENT_RESTRICTION:
                # logging.debug(f"skipping student {student_no} - not restricted")
                continue

            if student_no in existing_results:
                logging.debug(f"skipping student {student_no} - already tested")
                continue

            logging.debug(f"testing student {student_no}")
            test_results = run_tests(student_no, temp_dir, student_dir)
            existing_results[student_no] = test_results
            write_results(existing_results)


    except KeyboardInterrupt:
        logging.debug('keyboard interrupt received -> gracefully exiting...')
        return


def run_tests(student_no, temp_dir, student_dir):
    try:

        for code_dir in CUSTOM_CODE:
            removal = os.path.join(temp_dir, PROJECT, code_dir)
            logging.debug(f"removing {removal}")
            shutil.rmtree(removal)

            source = os.path.join(TARGET, student_dir, PROJECT, code_dir)
            logging.debug(f"copying {source} -> {removal}")
            shutil.copytree(source, removal)
            
        for overwrite in OVERWRITES:
            _src = overwrite
            _des = Path(temp_dir, PROJECT, overwrite.parent.name, overwrite.name)
            logging.debug(f"cpy {_src} -> {_des}")
            shutil.copy(overwrite, _des)


    except Exception as e:
        logging.debug("something went wrong during copying of student files, skipping tests")
        logging.debug(f"{str(e)}")

    # Run tests
    test_results = {'studentno': student_no}

    stdout_build = ""
    stderr_build = ""
    stdout_run = ""
    stderr_run = ""
    try:

        # for test_name, test_path, test_flags in TESTS:
        for test in TESTS:
            logging.debug(f"testing {test.name}")
            
            # cmd_build = [ DOTNET, 'build', os.path.join(temp_dir, PROJECT, test.path) ]

            # try:
            #     process_build = subprocess.run(cmd_build, capture_output=True, check=True) 
            # except Exception as e:
            #     logging.debug(f"build failed for test {test.name}. exception is '{e}'. continuing to next test...")
            #     continue

            cmd = test.to_cmd(temp_dir)
            logging.debug(f"running {cmd}")
            process_test = subprocess.run(cmd, stdout=PIPE, stderr=PIPE)            
            stdout_run = process_test.stdout.decode("utf-8")
            stderr_run = process_test.stderr.decode("utf-8")

            if f"test run timeout of {TIMEOUT} milliseconds exceeded" in stderr_run:
                logging.debug(f"timeout encountered for {test.name}")
                test_results[f"{test.name}_Passed"] = -1
                # test_results[f"{test.name}_Time"] = -1
                continue
                
            total_secs = re.search("Total time: (.*) Seconds", stdout_run)
            total_mins = re.search("Total time: (.*) Minutes", stdout_run)

            if total_secs:
                total_secs = float(total_secs.groups()[0])
            else:
                total_secs = float(total_mins.groups()[0]) * 60

            count_total = re.search("Total tests: ([0-9]+)", stdout_run).groups()[0]
            count_fail = re.search("Failed: ([0-9]+)", stdout_run)
            
            count_pass = 0
            if count_fail:
                count_pass = int(count_total) - int(count_fail.groups()[0])
            else:
                count_pass = re.search("Passed: ([0-9]+)", stdout_run).groups()[0]

            test_results[f"{test.name}_Passed"] = count_pass
            # test_results[f"{test.name}_Time"] = total_secs
            logging.debug(f"tests complete. passed: {count_pass}, time: {total_secs}")
    

    except Exception as e:
        logging.debug(f"something went during testing: {e}")

    return test_results


def main():
    temp_dir = prepare_project()
    existing_results = read_results()
    run_all_tests(temp_dir, existing_results)
    cleanup_project(temp_dir)


if __name__ == '__main__':
    main()
