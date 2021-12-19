# Cutie.py

## Description

This is a small tool that I wrote for myself in order to help with extracting the complete test plan from my org's QC ALM instance.

I took on this project since the ALM REST API is quite restrictive, and the interface is clunky to say the least.

I'm opensourcing this in hopes that someone that faced the same frustration in dealing with QC ALM finds this and can possibly make use of this tool.

## FAQ

- How do I use it?

  Create your mapping.yaml (or JSON) by checking your fields from within the ALM interface.

  Next, create a preferences.yaml (or JSON) by adding the necessary values (present in `class_def/preferences.py`) into it - This step is optional though.

  Run the command `cutie.py` without any arguments to get help on how to provide these files as arguments to the script.

- What's next? Moar features?

  I hope to extend the usage of this tool to cover other aspects like covering all CRUD operations on the ALM database.

  At the very least, I'll be adding some filtering options into the export operation.

- Why the name?

  Since cutie.py sounded like cutiepie.
