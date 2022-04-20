#!/usr/bin/env python3

import os
import zlib
import struct

def extractFile(inputFile):
	if type(inputFile) is str:
		file = open(inputFile, "rb")
	else:
		file = inputFile
	inputFileName = os.path.split(file.name)[1]
	size = os.fstat(file.fileno()).st_size
	
	order = ">"
	def readStruct(format, seek=None):
		if seek != None:
			file.seek(seek)
		return struct.unpack(order + format, file.read(struct.calcsize(order + format)))
	
	fileCount = readStruct("H", 0x16)[0]
	file.seek(0x60)
	for i in range(0, fileCount):
		name = file.read(0x40)
		index = name.find(0x0)
		if index != -1:
			name = name[:index]
		file.seek(0x10, os.SEEK_CUR)
		fsize = readStruct("5I")
		data = file.read(fsize[1] - 4)
		if fsize[0] > 0x50:
			try:
				data = zlib.decompress(data)
			except zlib.error:
				debugPrint("Error while extracting '{}' on file '{}': zlib decompress error".format(inputFileName, name.decode(errors="ignore")))
				raise
		yield {
			"name": name,
			"data": data
		}
		if file.tell() >= size:
			break

def existingDir(arg):
	if arg == "-" or os.path.isdir(arg):
		return arg
	else:
		raise argparse.ArgumentTypeError("Directory not found: '{}'".format(arg))

def strFileName(fileName):
	allowedSymbols = ("/", "-", "_", ".", " ")
	return "".join(x for x in fileName if x.isalnum() or x in allowedSymbols)

def debugPrint(*args, **kwargs):
	print(*args, file=sys.stderr, **kwargs)

if __name__ == "__main__":
	import argparse, sys
	
	parser = argparse.ArgumentParser()
	parser.add_argument(
		"file.drp",
		help="Path to a compressed DRP file",
		type=argparse.FileType("rb")
	)
	parser.add_argument(
		"-o",
		metavar="path",
		help="Set the path for the output uncompressed files, or set to '-' to print the output to stdout.",
		type=existingDir
	)
	parser.add_argument(
		"--ext",
		metavar="bin",
		help="Set the extension for the output uncompressed files, default is 'bin'.",
		default="bin"
	)
	parser.add_argument(
		"-v", "--debug",
		help="Print verbose debug information.",
		action="store_true"
	)
	if len(sys.argv) == 1:
		parser.print_help()
	else:
		args = parser.parse_args()
		inputFile = getattr(args, "file.drp")
		path = args.o
		drpContents = extractFile(inputFile)
		if not path:
			path = os.path.splitext(inputFile.name)[0]
			if not os.path.isdir(path):
				os.makedirs(path)
		unk = 0
		if args.debug and path != "-":
			debugPrint("Extracting '{}' to '{}'".format(os.path.split(inputFile.name)[1], path))
		for outFile in extractFile(inputFile):
			if path == "-":
				sys.stdout.buffer.write(outFile["data"])
			else:
				name = outFile["name"].decode(errors="ignore")
				outFileName = strFileName(name).strip("/")
				if not outFileName:
					unk += 1
					outFileName = "unknown{}".format(unk)
				outFilePath = os.path.join(path, "{}{}".format(outFileName, "." + args.ext if args.ext else ""))
				outFilePath = "/".join([x for x in outFilePath.split("/") if x != ".." and x != ""])
				if args.debug:
					debugPrint("Unpacking '{}' to '{}'".format(name, outFilePath))
				with open(outFilePath, "wb+") as out:
					out.write(outFile["data"])
