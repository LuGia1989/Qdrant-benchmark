# See if collections exist and points are growing
  curl -s http://10.80.120.102:6333/collections

  Then if a collection shows up:

  # Watch point count increase (replace COLLECTION_NAME)
  watch -n 5 'curl -s http://10.80.120.102:6333/collections/COLLECTION_NAME | python3 -m json.tool | grep points_count'
