# coding: utf-8

import fs
import os

# Make tests work even without installing the `fs.expose` module
fs.__path__.append(os.path.abspath(os.path.join(__file__, '..', '..', 'fs')))
