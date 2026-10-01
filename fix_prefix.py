#!/usr/bin/env python3
"""Fix prefix to use data_id (file ID like '黑B') instead of store abbreviation."""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "plugins/kadou/__init__.py"

with open(path, "r") as f:
    c = f.read()

# Fix matcher_query: city_id=name -> city_id=data_id
old_mq = """    prefix_text = await Reply("status.prefix", city_id=name)"""
new_mq = """    manifest = load_json(data_dir / "manifest.json")
    data_id = manifest.get(str(event.group_id), "")
    prefix_text = await Reply("status.prefix", city_id=data_id) if data_id else """""

assert old_mq in c, "matcher_query prefix not found!"
c = c.replace(old_mq, new_mq)
print("1/2 matcher_query prefix fixed")

# Fix matcher_list: city_id=name_key -> city_id=data_id
old_ml = """        prefix_text = await Reply("status.prefix", city_id=name_key)"""
new_ml = """        prefix_text = await Reply("status.prefix", city_id=data_id) if data_id else """""

assert old_ml in c, "matcher_list prefix not found!"
c = c.replace(old_ml, new_ml)
print("2/2 matcher_list prefix fixed")

with open(path, "w") as f:
    f.write(c)
print(f"\n{path} written successfully")