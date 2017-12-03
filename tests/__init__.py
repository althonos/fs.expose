# coding: utf-8

import fs
import os

fs.__path__.append(os.path.abspath(os.path.join(__file__, '..', '..', 'fs')))
print(fs.__path__)
