# Cutie.py

## Description

This is a small tool that I wrote for myself in order to help with extracting the complete test plan from my org's QC ALM instance.

I took on this project since the ALM REST API is quite restrictive, and the interface is clunky to say the least.

I'm opensourcing this in hopes that someone that faced the same frustration in dealing with QC ALM finds this and can possibly make use of this tool.

## Requirements

Python version(s) 3.7 and above should be supported, but not tested - 3.9 and above is tested.

The following libraries are used in this tool:
 - [rich](https://pypi.org/project/rich/)
 - [beautifulsoup4](https://pypi.org/project/beautifulsoup4/)
 - [requests](https://pypi.org/project/requests/)
 - [xlsxwriter](https://pypi.org/project/XlsxWriter/)
 - [lxml](https://pypi.org/project/lxml/)
 - [yaml](https://pypi.org/project/PyYAML/)
 - [yamlloader](https://pypi.org/project/yamlloader/)

Install them in your Python environment before you start using this tool.

## FAQ

- **How do I use it?**

  Install the required libraries mentioned in the *Requirements* section into your preferred Python environment.

  Generate the default `preferences.yaml` file using the command `python cutie.py -g`.

  Customize the preferences file obtained to match your ALM and network environment.

  Once done, run `python cutie.py` to get help on how to use the tool.

  Example invocation for test plan export: `python cutie.py -p preferences.yaml -o output.xlsx`

- **What's next? Moar features?**

  I hope to extend the usage of this tool to cover other aspects like covering all CRUD operations on the ALM database.

  At the very least, I'll be adding some filtering options into the export operation.

- **Why the name?**

  Since cutie.py sounded like cutiepie.
