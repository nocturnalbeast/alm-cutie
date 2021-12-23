import collections
import logging
from re import sub
import yamlloader
from collections import OrderedDict
from getpass import getuser
from os import path as os_path
from rich.prompt import Confirm, Prompt
from yaml import dump, load

from libs.pathops import is_path_exists_or_creatable

# this is the default options dictionary
# options are specified as key-value pairs where the key is a hierarchial path of the key instead of the key name only
# this is then supplied to the defopt_parser method which will convert it into a nested dictionary based on the path given
# if any new options are to be defined or if a default value of an existing key is to be updated, do it here and then generate the YAML configuration file.
DEFAULT_OPTS = {
    "alm/https_strict": False,
    "mapping/Feature code": "user-12",
    "mapping/Test case ID": "user-10",
    "mapping/Test name": "name",
    "mapping/Creation date": "creation-time",
    "mapping/Type": "subtype-id",
    "mapping/Test mode": "user-09",
    "mapping/Test level": "user-06",
    "mapping/Test execution time": "user-13",
    "mapping/Requirement ID": "user-14",
    "mapping/Config interface": "user-01",
    "mapping/IP version": "user-05",
    "mapping/LAN interface": "user-02",
    "mapping/ALM internal ID": "id",
    "mapping/WAN connection": "user-04",
    "mapping/WAN mode": "user-03",
    "mapping/Test title": "user-16",
    "mapping/Test type": "user-15",
    "mapping/Owner": "owner",
    "mapping/Description": "description",
    "email/to_list": [],
    "email/cc_list": [],
    "email/smtp_port": 25,
}

# this is the list of keys that should be there in a ConfigStore instance
# we will use the DEFAULT_OPTS dictionary as a source for fallback values
REQUIRED_KEYS = [
    "alm/domain",
    "alm/webdomain",
    "alm/project",
    "alm/tests_folder",
    "alm/https_strict",
    "alm/username",
    "alm/password",
    "email/sender_domain",
    "email/to_list",
    "email/cc_list",
    "email/smtp_host",
    "email/smtp_port",
]


def merge_dicts(orig_dict: dict, update_dict: dict) -> dict:
    """Merge (or update) two dictionaries together.

    Args:
        orig_dict (dict): The original dictionary.
        update_dict (dict): The dictionary with the updated data.

    Returns:
        dict: The merged dictionary.
    """
    # iterate through the dict with the updated data
    for key, value in update_dict.items():
        # check if value is a subdict
        if isinstance(value, collections.abc.Mapping):
            # if yes, then recursively call the function with the subdicts of each respective dicts
            orig_dict[key] = merge_dicts(orig_dict.get(key, OrderedDict()), value)
        else:
            # if no, then just assign/update the value directly
            orig_dict[key] = value
    # finally return the updated/merged dictionary
    return orig_dict


def defopt_parser(defopts: dict) -> dict:
    """Generates a nested dictionary ready to be written to a configuration file using the yaml module.

    Args:
        defopts (dict): The input dictionary - this will have nested values as paths instead of actual subdictionaries. Refer the above default value dictionaries for examples.

    Returns:
        dict: The nested dictionary which can be directly pushed to yaml module.
    """
    # start with an empty dict
    result_dict = OrderedDict()
    # iterate through each path that is specified in the input dictionary
    for key in defopts.keys():
        # split the path into constituent parts
        path_keys = key.split("/")
        # move the data key i.e. the last part of the path into another variable
        data_key = path_keys[-1]
        # keep the other parts in the same list
        path_keys = path_keys[:-1]
        # start building the nested dictionary which contains only the elements in the path and it's respective data by creating the innermost child with the data key and the data
        update_dict = OrderedDict()
        update_dict[data_key] = defopts[key]
        # now iterate through each part in the reversed order, building the dictionary from the inside as we progress
        for key in reversed(path_keys):
            outer_dict = OrderedDict()
            outer_dict[key] = update_dict
            update_dict = outer_dict
        # merge/update the dictionary created thus into the result dictionary that we declared at the start
        merge_dicts(result_dict, update_dict)
    # once we are done with all entries, we have built the nested dictionary as required - so we return that
    return result_dict


def write_default_config(output_path: str):
    """Writes the default configuration to a given file.

    Args:
        output_path (str): The path to the output file that the configuration is written to.
    """
    log = logging.getLogger("cutie-configuration")
    # check if path is valid
    if is_path_exists_or_creatable(output_path):
        # if the path is a folder - set the path as folder/preferences.yaml
        if os_path.isdir(output_path):
            output_path = output_path + os_path.sep + "preferences.yaml"
        # if the path is a file
        if os_path.isfile(output_path):
            # prompt the user to confirm before overwriting it
            if not Confirm.ask(
                "Existing configuration file found at specified path, overwrite file?"
            ):
                log.warning("New configuration file not generated.")
                return
        # now open a file stream and dump the data
        with open(output_path, "w+") as config_file:
            config_file.write(
                dump(
                    defopt_parser(DEFAULT_OPTS),
                    Dumper=yamlloader.ordereddict.CDumper,
                    indent=4,
                    default_flow_style=False,
                )
            )
        log.info(f"Configuration file written to {os_path.abspath(output_path)}")


def create_object(value: dict):
    """Creates a 'nested' object given a nested dictionary. Useful when the keys are to be referenced using direct notation instead of the dictionary get() or dict[key] methods.

    Args:
        value (dict): The dictionary that is to be converted to the object.

    Returns:
        object: The 'nested' object.
    """
    # check if the value passed is a dictionary
    if isinstance(value, dict):
        # if yes, then define a simple Object class
        class Object(dict):
            def __setitem__(self, key, val):
                setattr(self, key, val)
                return super(Object, self).__setitem__(key, val)

        # declare an instance of the class thus defined
        ret_obj = Object()
        # iterate through the dictionary key-value pairs
        for key, val in value.items():
            # if the value in a key-value pair is another dictionary
            if isinstance(val, dict):
                # recursively call the function to resolve conversion of the inner dict to object
                ret_obj[key] = create_object(val)
            # if not, then assign the value to the key
            else:
                ret_obj[key] = val
            # now set the value as an attribute of the object dynamically
            setattr(ret_obj, key, ret_obj[key])
        # return the object
        return ret_obj
    # if it's not a dictionary, then return the value as-is
    else:
        return value


class ConfigStore:
    """A data class to store the configuration defined in the configuration file during runtime, so that modifications to it during runtime don't affect the running instance."""

    # keep a backup of the dictionary
    raw_data = None

    def __init__(self, config_path):
        # have a logger ready before initializing the instance
        log = logging.getLogger("cutie-configuration")
        # better to go the EAFP route here
        try:
            with open(config_path) as config:
                # load the configuration YAML file into the raw_data - the loader will return the nested dictionary
                self.raw_data = load(config, Loader=yamlloader.ordereddict.CLoader)
                # get the fallback values
                fallback_config = defopt_parser(
                    {
                        key: DEFAULT_OPTS[key]
                        for key in REQUIRED_KEYS
                        if key in DEFAULT_OPTS.keys()
                    }
                )
                # apply the fallback values to the current config by overlaying the current config dictionary on top of the fallback values dictionary
                self.raw_data = merge_dicts(fallback_config, self.raw_data)
                # config interactive mode in case defopts doesn't have it as well
                interactive_config = {}
                for key in REQUIRED_KEYS:
                    key = key.split("/")
                    leaf_val = self.raw_data
                    for subkey in key:
                        leaf_val = leaf_val.get(subkey)
                    # enter interactive mode here
                    if leaf_val is None:
                        fullkey = "/".join(key)
                        log.info(
                            f"Value for field {fullkey} empty and not found in fallback preferences, moving to interactive mode."
                        )
                        if key[-1] == "password":
                            interactive_config.update(
                                {
                                    fullkey: Prompt.ask(
                                        f"Password [{fullkey}]", password=True
                                    ),
                                }
                            )
                        elif key[-1] == "username":
                            username = getuser()
                            log.info(
                                f"Autodetected username [{fullkey}] as {username} from system."
                            )
                            if Confirm.ask("Is this username correct?"):
                                interactive_config.update({fullkey: username})
                            else:
                                interactive_config.update(
                                    {fullkey, Prompt.ask(f"Username [{key}]")}
                                )
                        else:
                            interactive_config.update({fullkey: Prompt.ask(f"{key}")})
                # merge the key-value pairs obtained from interactive mode with the main data
                self.raw_data = merge_dicts(
                    self.raw_data, defopt_parser(interactive_config)
                )
        except Exception as e:
            print(e)
            log.error("Could not load configuration!")
        # now iterate through the keys that we got from the nested dict
        for key in self.raw_data.keys():
            # the 'general' keyword is used as an escape to extract key-value pairs directly onto the root/parent object
            # so, this handles it accordingly assuming the key encountered is the same
            if key == "general":
                gen_data = self.raw_data["general"]
                for subkey in gen_data.keys():
                    setattr(self, subkey, create_object(gen_data[subkey]))
            # if not, then convert to objects using create_object method
            else:
                setattr(self, key, create_object(self.raw_data[key]))
