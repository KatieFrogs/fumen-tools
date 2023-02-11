#!/usr/bin/env python3

import os, sys, struct, argparse
import glob
import math
from functools import cmp_to_key

konga2tja_version = "v1.1"

noteTypes = {
	0x00: "0",
	0x01: "2", # Pa, パ
	0x02: "2", # Pa, パッ
	0x03: "2", # Pa, パン
	0x04: "1", # Pon, ポ
	0x05: "1", # Pon, ポッ
	0x06: "1", # Pon, ポン
	#0x07: "0",
	#0x08: "0",
	#0x09: "0",
	#0x0A: "0",
	#0x0B: "0",
	#0x0C: "0",
	0x0D: "4", # Clap, チャ
	0x0E: "4", # Clap, チャッ
	0x0F: "4", # Clap, チャン
	0x10: "3", # Pink, D
	#0x11: "0", # Unhittable Barrel
	0x12: "I", # Pa Drumroll, 連打
	0x13: "5", # Pon Drumroll, 連打
	#0x14: "0",
	#0x15: "0",
	0x16: "H", # Clap Drumroll, 拍手
	0x17: "6", # Pink Drumroll, 連打
	#0x18: "0", # Unhittable Barrel Drumroll
	0x19: "1", # Pow block
	0x1A: "2", # Stop Pa, パ
	0x1B: "4", # Stop Clap, チャ
	0x1C: "1", # Stop Pon, ポン
	0x1D: "6"  # Pink Drumroll (brings up the counter)
}
drumrolls = ["I", "5", "H", "6"]

def parseBin(filename, force=False, verbose=False, addBpm=False, addDelay=False, rounding=5, bpm=None):
	file = open(filename, "rb")
	size = os.fstat(file.fileno()).st_size
	
	def readStruct(format, seek=None):
		if seek:
			file.seek(seek)
		return struct.unpack(order + format, file.read(struct.calcsize(order + format)))
	
	order = ">"
	output = {
		"bpm": None,
		"offset": 0
	}
	chart = []
	magic = readStruct("I")[0]
	
	frame = 1 / 60
	spawnToOffset = 0.6095
	offset = 0
	spawnOffset = 0
	tja = []
	commands = []
	isDrumroll = None
	barline = True
	
	if magic == 0x20030730:
		while True:
			spawn, showLine, framesPerMeasure = readStruct("HBB")
			if spawn == 0xffff:
				break
			
			command = []
			prevBpm = bpm
			bpm = 240 / (framesPerMeasure * frame)
			prevSpawnOffset = spawnOffset
			spawnOffset = max(2, math.floor(spawn * spawnToOffset)) * frame
			if len(commands) == 0:
				offset = spawnOffset + 240 / bpm
			else:
				offset = spawnOffset + 240 / bpm - prevSpawnOffset - 240 / prevBpm
				posBpm = offset - 240 / prevBpm
			
			if prevBpm == None:
				output["bpm"] = round(bpm, rounding)
			elif addBpm and round(prevBpm, rounding) != round(bpm, rounding):
				command.append("#BPMCHANGE {}".format(round(bpm, rounding)))
			
			if len(commands) == 0:
				output["offset"] = round(-offset, rounding)
			elif addDelay and round(posBpm, rounding) != 0:
				command.append("#DELAY {}".format(round(posBpm, rounding)))
			
			if barline and not showLine:
				command.append("#BARLINEOFF")
				barline = False
			elif not barline and showLine:
				command.append("#BARLINEON")
				barline = True
			
			if verbose:
				command.append("// #{}, spawn: {}s, offset: {}s, measure: {} frames".format(
					len(commands) + 1,
					round(math.floor(spawn * spawnToOffset) * frame, 3),
					round(offset, 3),
					framesPerMeasure
				))
			
			notes = readStruct("48B")
			for i in range(len(notes)):
				try:
					noteTja = noteTypes[notes[i]]
				except KeyError:
					info = "//unknown note {:x} at offset {:x}".format(notes[i], file.tell() - 48 + i)
					print(info)
					command.append(info)
					noteTja = "?"
					if not force:
						raise
				if noteTja in drumrolls:
					if isDrumroll == noteTja:
						tja.append("0")
					elif isDrumroll:
						if tja[-1] == "0":
							tja[-1] = "8"
						tja.append(noteTja)
						isDrumroll = noteTja
					else:
						tja.append(noteTja)
						isDrumroll = noteTja
				elif isDrumroll:
					if tja[-1] == "0":
						tja[-1] = "8"
					tja.append(noteTja)
					isDrumroll = None
				else:
					tja += noteTja
			
			commands.append(command)
			
			if file.tell() >= size:
				break
		if isDrumroll:
			tja[-1] = "8"
		
		tja = [tja[i : i + 48] for i in range(0, len(tja), 48)]
		for i in range(len(tja)):
			for line in commands[i]:
				chart.append(line)
			chart.append(compress(tja[i]) + ",")
	else:
		chart.append("//magic {:x}".format(magic))
		if not force:
			raise Exception("Magic does not match")
	file.close()
	
	output["chart"] = "\n".join(chart)
	return output

def compress(notes):
	notes = reduceNotes(notes, 2)
	notes = reduceNotes(notes, 3)
	notes = "".join(notes)
	return "" if notes == "0" else notes

def reduceNotes(notes, amount):
	while len(notes) >= amount and len(notes) % amount == 0:
		for i in range(len(notes) - 1, 0, -amount):
			for j in range(amount - 1):
				if notes[i - j] != "0":
					return notes
		for i in range(len(notes) - 1, 0, -amount):
			for j in range(amount - 1):
				del notes[i - j]
	return notes

def existingFile(arg):
	if "*" in arg or "?" in arg:
		argGlob = glob.glob(arg)
		if argGlob:
			return argGlob
	elif os.path.isfile(arg):
		return arg
	raise argparse.ArgumentTypeError("File not found: '{}'".format(arg))

def fileReplace(filename):
	path,ext = os.path.splitext(filename)
	if path.endswith("_h"):
		return path[:-2] + "_0" + ext
	elif path.endswith("_n"):
		return path[:-2] + "_1" + ext
	elif path.endswith("_e"):
		return path[:-2] + "_2" + ext
	return filename

def sortFiles(a, b):
	return (1 if fileReplace(a) > fileReplace(b) else -1)

if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="konga2tja {0}".format(konga2tja_version)
	)
	parser.add_argument(
		"file.bin",
		nargs="+",
		type=existingFile,
		help="Path to a Donkey Konga bin file"
	)
	parser.add_argument(
		"--force", "-f",
		action="store_true",
		help="Ignore errors"
	)
	parser.add_argument(
		"--dryrun",
		action="store_true",
		help="Test the parser without writing"
	)
	parser.add_argument(
		"--verbose", "-v",
		action="store_true",
		help="Print additional information"
	)
	group = parser.add_mutually_exclusive_group()
	group.add_argument(
		"--bpm",
		action="store_true",
		default=True,
		help="Add BPM information (default)"
	)
	group.add_argument(
		"--no-bpm",
		dest="bpm",
		action="store_false",
		help="Remove BPM information"
	)
	group = parser.add_mutually_exclusive_group()
	group.add_argument(
		"--delay",
		action="store_true",
		default=True,
		help="Add delay information (default)"
	)
	group.add_argument(
		"--no-delay",
		dest="delay",
		action="store_false",
		help="Remove delay information"
	)
	parser.add_argument(
		"--rounding",
		metavar="5",
		type=int,
		default=5,
		help="Round numbers to a given precision"
	)
	if len(sys.argv) == 1:
		parser.print_help()
	else:
		args = parser.parse_args()
		outFile = None
		output = None
		name = None
		bpm = None
		offset = None
		
		input = getattr(args, "file.bin")
		inputFiles = []
		for file in input:
			if type(file) is list:
				inputFiles.extend(file)
			else:
				inputFiles.append(file)
		inputFiles = sorted(inputFiles, key=cmp_to_key(sortFiles))
		
		for filename in inputFiles:
			print(filename)
			prevOutFile = outFile
			prevName = name
			
			outFile,ext = os.path.splitext(filename)
			if outFile.endswith("_h") or outFile.endswith("_n") or outFile.endswith("_e"):
				outFile = outFile[:-2]
			if ext == ".bin":
				ext = ""
			outFile = outFile + ext + ".tja"
			name = os.path.splitext(os.path.split(outFile)[1])[0]
			
			if prevOutFile != outFile:
				if output and not args.dryrun:
					with open(prevOutFile, "w+") as file:
						file.write("\n".join(output))
				output = [
					"TITLE:{}".format(name),
					"SUBTITLE:--",
					"BPM:",
					"WAVE:{}.ogg".format(name),
					"OFFSET:-0",
					"DEMOSTART:0",
					"GAME:Bongo",
					""
				]
				bpm = None
				offset = None
			
			course = ""
			chartName = os.path.splitext(os.path.split(filename)[1])[0]
			if chartName.endswith("_h"):
				course = "Hard"
			elif chartName.endswith("_n"):
				course = "Normal"
			elif chartName.endswith("_e"):
				course = "Easy"
			tja = parseBin(filename, args.force, args.verbose, args.bpm, args.delay, args.rounding, bpm)
			
			if bpm == None and tja["bpm"]:
				bpm = tja["bpm"]
				output[2] += str(bpm)
			if offset == None and tja["offset"]:
				offset = tja["offset"]
				output[4] = output[4][:-2] + str(offset)
			
			output += [
				"COURSE:{}".format(course),
				"LEVEL:",
				"BALLOON:",
				"SCOREINIT:",
				"SCOREDIFF:",
				""
			]
			if args.verbose:
				output.append("//" + filename)
			output += [
				"#START",
				"#GAMETYPE Konga",
				tja["chart"],
				"#END",
				""
			]
		output = "\n".join(output)
		if output and not args.dryrun:
			with open(outFile, "w+") as file:
				file.write(output)
