"""Support for reading TOSCA translator configuration file"""

import yaml

def read_tosca_config(config_file_name):
    """Read the configuration file for the YANG to TOSCA translator
    """

    # Open config file
    try:
        config_file = open(config_file_name)
    except Exception as e:
        print("Unable to open '%s': %s" % (config_file_name, str(e)))
        return None

    # Read data from the config file
    try:
        config_file_data = config_file.read()
    except Exception as e:
        print("Unable to read '%s': %s" % (config_file_name, str(e)))
        return None

    # Return parsed file content as YAML.
    try:
        yaml_data = yaml.load(config_file_data, Loader=yaml.FullLoader)
    except Exception as e:
        print("Unable to parse '%s': %s" % (config_file_name, str(e)))
        return None

    # All done
    return yaml_data


