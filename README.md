yang2tosca
===

`yang2tosca` is a tool for converting YANG modules to TOSCA type
definitions. While it is packaged as a standalone tool, it is built as
a [pyang](https://github.com/mbj4668/pyang) plugin.

A typical conversion will involve two steps:

1. First, YANG models are converted automatically by yang2tosca to
   (almost) equivalent TOSCA date type definitions.

2. Next, service designers must (manually) convert some of the
   resulting TOSCA data types into node types, relationship types,
   requirements, and capabilities. This step requires knowledge of
   service-specific semantics and cannot be automated.

# Installing yang2tosca

## Setting up a virtual environment

``yang2tosca`` is written in Python3. We recommend that you run the
``yang2tosca`` software in its own virtual environment. To support
virtual environments, install the python virtual environments module
as follows:

    sudo apt install python3-venv

You can then create and activate your virtual environment as follows:

    python3 -m venv env
    source env/bin/activate
    
``yang2tosca`` uses [PEP-517](https://www.python.org/dev/peps/pep-0517/)
and [PEP-518](https://www.python.org/dev/peps/pep-0518/) based
installation systems that require the latest version of ``pip``. To
upgrade ``pip`` to the latest version, run the following command in
your virtual environment:

    pip install -U pip 

The ubicity software can be installed directly from the git repository
by running the following command in your virtual environment:

    pip install git+https://github.com/lauwers/ubicity
    
Alternatively, you can also clone the git repo first and then run the
installer in your local copy as follows:

    git clone https://github.com/lauwers/ubicity
    cd ubicity
    pip install . 
    
## Downloading the software

The yang2tosca software can be installed directly from the git repository
by running the following command in your virtual environment:

    pip install git+https://github.com/lauwers/yang2tosca
    
Alternatively, you can also clone the git repo first and then run the
installer in your local copy as follows:

    git clone https://github.com/lauwers/yang2tosca
    cd yang2tosca
    pip install . 
    
## Using yang2tosca

Convert a YANG module to a TOSCA service template as follows:

```
yang2tosca [ --config|-c <config_file> ] <yang_file> [<tosca_file>]
```
If no tosca_file is specified, the output will be directed to stdout.

The config file uses YAML to define:

1. How YANG types are mapped to TOSCA types

2. Which profiles need to be included in the TOSCA output.

If no config file is specified, ``yang2tosca`` uses the following built-in file:


