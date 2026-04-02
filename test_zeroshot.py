from parseforge.layers.parser import process
import os
os.environ["HF_HUB_OFFLINE"] = "1"

res1 = process("Find me a senior embedded C++ and WebGL engineer to build an engine")
print(f"Goal Topic Extraction (Zero Shot): {res1.topic}")

res2 = process("I need some quick frontend UI styling with tailwind CSS")
print(f"Goal Topic Extraction (Zero Shot): {res2.topic}")
