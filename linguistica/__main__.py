#!/usr/bin/env python3
# -*- encoding: utf8 -*-

import sys

import linguistica as lxa
from linguistica.gui import main as gui_main
from linguistica.cli import main as cli_main
from linguistica.util import check_py_version

check_py_version()

lxa_version = lxa.__version__

# ------------------------------------------------------------------------------
# ensure lxa_mode is one of the modes in MODES

MODES = {'cli', 'gui'}

try:
    lxa_mode = sys.argv[1].lower()
except IndexError:
    lxa_mode = None
    error_msg_template = 'Error: mode not specified for running Linguistica.' \
                         '\n\nRun one of the following:\n\n{}'
    command_template = 'python3 -m linguistica {}'

    sys.exit(error_msg_template.format('\n'.join([command_template.format(mode)
                                                  for mode in sorted(MODES)])))

if lxa_mode not in MODES:
    sys.exit('Unrecognized mode: ' + sys.argv[1])

# ------------------------------------------------------------------------------
# launch graphical user interface

if lxa_mode == 'gui':
    print('Running the graphical user interface of Linguistica {}...'
          .format(lxa_version))
    gui_main()

# ------------------------------------------------------------------------------
# launch command line interface

if lxa_mode == 'cli':
    cli_main()
