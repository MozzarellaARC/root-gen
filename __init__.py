bl_info = {
    "name": "Root Gen",
    "category": "Animation",
    "author": "Manas R. Makde, MozzarellaARC",
    "version": (1, 1, 0),
    "description": "An add-on for creating a root bone and baking it into existing actions"
}


import bpy
from .core.root_gen import *

def register():
    register_root_gen()

def unregister():
    unregister_root_gen()