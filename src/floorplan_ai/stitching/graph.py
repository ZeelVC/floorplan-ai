from __future__ import annotations
def components(node_count,edges):
 parent=list(range(node_count))
 def root(x):
  while parent[x]!=x: parent[x]=parent[parent[x]];x=parent[x]
  return x
 for a,b in edges:
  a,b=root(a),root(b)
  if a!=b:parent[b]=a
 return tuple(tuple(i for i in range(node_count) if root(i)==r) for r in sorted({root(i) for i in range(node_count)}))
