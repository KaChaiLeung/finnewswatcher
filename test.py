from finnewswatcher.config import load_sources
srcs = load_sources()
print(len(srcs), srcs[0].name, srcs[0].type, srcs[0].url.host)