from parseforge.layers.parser import process
from parseforge.layers.schema import IntentEnum
import os
os.environ["HF_HUB_OFFLINE"] = "1"

print("Parsing garbage ('hello world random text')...")
res1 = process("hello world random text")
print(f"Result intent: {res1.intent.value}, confidence: {res1.parse_confidence}")

print("Parsing project ('project robotics weekend')...")
res2 = process("I want to build a robotics project this weekend")
print(f"Result intent: {res2.intent.value}, confidence: {res2.parse_confidence}")

print("Done testing!")
