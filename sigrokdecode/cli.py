import sys
if sys.version_info < (3, 10):
    from importlib_metadata import entry_points
else:
    from importlib.metadata import entry_points

discovered_plugins = entry_points(group='pysigrok.decoders')

def main():
    print("hello world")
    for p in discovered_plugins:
        print(p)
        loaded = p.load()
        print(loaded)
        print(loaded.name, loaded.longname, loaded.desc)
