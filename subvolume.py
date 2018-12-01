#!/usr/bin/python3

import btrfs
import os
import sys
from collections import OrderedDict

#path of btrfs filesystem
path = sys.argv[1]


#list of ingored subvolumes
ignored_trees=set()

for item in sys.argv[2:]:
	ignored_trees.add(int(item))

fs = btrfs.FileSystem(path)
subvolume_extent_dictionary=OrderedDict()

#iterate all subvolumes

for subvol in fs.subvolumes():
	tree = subvol.key.objectid
	if tree in ignored_trees:
		continue
	#print(subvol)
	#print(tree)
	extent_set=set()
	#search in this subvolume all file extents
	for header, data in btrfs.ioctl.search_v2(fs.fd, tree):
		if header.type == btrfs.ctree.EXTENT_DATA_KEY:
			datum=btrfs.ctree.FileExtentItem(header,data)
			#print(datum)
			#ignore inline file extents, they are small
			if datum.type != btrfs.ctree.FILE_EXTENT_INLINE:
				pair=(header.objectid,datum.logical_offset,datum.disk_num_bytes)
				#print(pair)
				#print(datum)
				extent_set.add(pair)
	#print(extent_set)
	subvolume_extent_dictionary[tree]=extent_set

#print(subvolume_extent_dictionary)

#make sure that subvolume order is from newest (current) to oldest

trees=list(subvolume_extent_dictionary.keys())
current_tree=trees[0]
del trees[0]
trees.append(current_tree)
trees.reverse()
#print(trees)
#sys.exit(0)

#parse list of subvolumes and calculate the number of the unique file extents in this subvolume
subvolume_extent_dictionary_sizes=OrderedDict()
for index,snapshot in enumerate(trees):
	previous_snapshot = trees[index-1]
	if index==0:
		previous_snapshot = None
	try:
		next_snapshot = trees[index+1]
	except:
		next_snapshot = None
	#print(index,snapshot,previous_snapshot,next_snapshot)
	if previous_snapshot != None and next_snapshot != None :
		subvolume_extent_dictionary_sizes[snapshot]= subvolume_extent_dictionary[snapshot] - subvolume_extent_dictionary[previous_snapshot] - subvolume_extent_dictionary[next_snapshot]
		#subvolume_extent_dictionary_sizes[snapshot].union(subvolume_extent_dictionary[snapshot] - subvolume_extent_dictionary[next_snapshot])
	elif previous_snapshot == None:
		subvolume_extent_dictionary_sizes[snapshot]=subvolume_extent_dictionary[snapshot] - subvolume_extent_dictionary[next_snapshot]
	else:
		subvolume_extent_dictionary_sizes[snapshot]= subvolume_extent_dictionary[snapshot] - subvolume_extent_dictionary[previous_snapshot]
	#calculate the sum of unique file extents for each subvolume
	sum=0
	for extent in subvolume_extent_dictionary_sizes[snapshot]:
		sum+=extent[2]
	print(snapshot,sum,len(subvolume_extent_dictionary_sizes[snapshot]))
