# yang2tosca

`yang2tosca` is a [pyang](https://github.com/mbj4668/pyang) plugin for
converting YANG modules to TOSCA.

## Installation

`yang2tosca` requires Python 3. I recommend running yang2tosca inside a
virtual environment. Create the virtual environment as follows:

```
python3 -m venv y2t
source y2t/bin/activate
pip install wheel
pip install pyang
pip install stringcase
```

## Usage

Specify TOSCA as the desired pyang output format as follows:

```
pyang -f tosca --plugindir <install_dir>/yang2tosca/plugins/ <yang_file> -o <yaml_file>
```
