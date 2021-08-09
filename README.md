# yang2tosca

`yang2tosca` is a [pyang](https://github.com/mbj4668/pyang) plugin for
converting YANG modules to TOSCA files.

A typical conversion will involve two steps:

1. First, YANG models are converted automatically by yang2tosca to
   (almost) equivalent TOSCA date type definitions.

2. Next, service designers must (manually) convert some of the
   resulting TOSCA data types into node types, relationship types,
   requirements, and capabilities. This step requires knowledge of
   service-specific semantics and cannot be automated.

## Installation

`yang2tosca` requires Python 3. We recommend running yang2tosca inside a
virtual environment. Create the virtual environment as follows:

```
python3 -m venv env
source env/bin/activate
pip install wheel
pip install pyang
pip install stringcase
```

## Usage

Specify TOSCA as the desired pyang output format as follows:

```
pyang -f tosca --plugindir <install_dir>/yang2tosca/plugins/ <yang_file> -o <tosca_file>
```
