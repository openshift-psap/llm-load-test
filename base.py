# pylint: disable=too-few-public-methods,empty-docstring,too-many-arguments

"""
"""
import json
import os
import sys
import uuid
import yaml


class Base():
    """
    Utility functions
    """

    def _exit_failure(self, msg):
        """
        """
        logging.error(msg)
        sys.exit(1)

    def _create_temp_directory(self, working_directory=None):
        """
        """

        if not working_directory:
            sys.exit(1)
        temp_dir = os.path.join(working_directory, str(uuid.uuid4()))
        try:
            os.mkdir(temp_dir)
        except FileExistsError:
            logging.error("Proposed working directory already exists, exiting")
            sys.exit(1)
        except FileNotFoundError:
            logging.error("No such directory")
            sys.exit(1)
        return temp_dir

    def _yaml_load(self, file):
        """
        Simple YAML loader
        """
        if not os.path.isfile(file):
            raise FileNotFoundError(file)
        with open(file, 'r', encoding="utf-8") as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError:
                raise RuntimeError(f"Could not parse {file}") \
                    # pylint: disable=raise-missing-from

    def _json_load(self, file):
        """
        Simple JSON loader
        """
        if not os.path.isfile(file):
            raise FileNotFoundError(file)
        with open(file, "r", encoding="utf-8") as stream:
            try:
                return json.load(stream)
            except json.JSONDecodeError:
                raise RuntimeError(f"Could not parse {file}") \
                    # pylint: disable=raise-missing-from

    def _json_dump(self, dictionary, file, overwrite=False):
        """
        Simple JSON file writer
        #TODO JSON + write error checking
        """
        json_object = json.dumps(dictionary, indent=4)

        if os.path.isfile(file) and not overwrite:
            raise RuntimeError(file)
        with open(file, "w", encoding="utf-8") as outfile:
            outfile.write(json_object)

