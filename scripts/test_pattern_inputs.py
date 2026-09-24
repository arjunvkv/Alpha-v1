import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r"C:\Trading\Alpha")
from mcp_server.graphiti_mcp_server import search_facts

print("Test 1 (comma string):")
print(search_facts(patterns="BSL_SWEEP, 4TF_BEARISH"))

print("\nTest 2 (json string):")
print(search_facts(patterns="['BSL_SWEEP', '4TF_BEARISH']"))
