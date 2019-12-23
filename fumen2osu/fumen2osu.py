import os, sys, struct

fumen2osu_version = "v1.0"
usage = """fumen2osu {0}
py {1} file_m.bin [offset] [/title "Title"] [/wave file.wav] [/debug]

file_m.bin       Path to Taiko no Tatsujin fumen file.
offset           Note offset in seconds, negative values will make the notes
                 appear later. Example: -1.9
/title "Title"   Set the title in the output file.
/wave file.wav   Set the audio filename in the output file.
/debug           Print verbose debug information."""

def readFumen(filename, globalOffset=0, title="", wave="", debug=False):
	if not os.path.isfile(filename):
		print("Error: Cannot find file {0}".format(filename))
		return
	
	try:
		globalOffset = float(globalOffset) * 1000.0
	except ValueError:
		print("Error: Could not convert offset {0} to float".format(globalOffset))
		return
	
	filenameNoExt = os.path.splitext(filename)[0]
	
	with open(filename, "rb") as file:
		size = os.fstat(file.fileno()).st_size
		noteTypes = {
			0x1: "Don", # ドン
			0x2: "Don", # ド
			0x3: "Don", # コ
			0x4: "Ka", # カッ
			0x5: "Ka", # カ
			0x6: "Drumroll",
			0x7: "DON",
			0x8: "KA",
			0x9: "DRUMROLL",
			0xa: "Balloon",
			0xb: "DON", # hands
			0xc: "Kusudama",
			0xd: "KA" # hands
		}
		start = 0x208
		scoreInit = 0
		scoreDiff = 0
		totalBars = readByte(file, 0x200, 4, "int")
		bars = []
		if debug:
			print("Total bars: {0}".format(totalBars))
		
		for barNumber in range(totalBars):
			bar = {}
			# barStruct: bpm 4, offset 4, gogo 1, hidden 1, dummy 2, branches 4 * 6, dummy 4, totalNotes 2, dummy 2, speed 4
			barStruct = struct.unpack(">ffBBHiiiiiiiHHf", readByte(file, start, 0x30))
			bar["bpm"] = barStruct[0]
			bar["offset"] = barStruct[1]
			gogo = barStruct[2]
			bar["gogo"] = True if gogo == 1 else False if gogo == 0 else gogo
			hiddenBar = barStruct[3]
			bar["hiddenBar"] = True if hiddenBar == 1 else False if hiddenBar == 0 else hiddenBar
			totalNotes = barStruct[12]
			bar["speed"] = barStruct[14]
			
			if debug:
				print("")
				print("Bar #{0} at {1}-{2} ({3})".format(barNumber, shortHex(start), shortHex(start + 0x3f + 0x18 * totalNotes), nameValue(bar)))
				print("Total notes: {0}".format(totalNotes))
			
			start += 0x30
			
			for barIndex in range(totalNotes):
				if debug:
					print("Note #{0} at {1}-{2}".format(barIndex, shortHex(start), shortHex(start + 0x17)), end="")
				note = {}
				# noteStruct: type 4, pos 4, dummy 8, init 2, diff 2, length 4
				noteStruct = struct.unpack(">ifQHHf", readByte(file, start, 0x18))
				type = noteStruct[0]
				if not type in noteTypes:
					if debug:
						print("")
					print("Error: Unknown note type '{0}' at offset {1}".format(shortHex(type).upper(), hex(start)))
					return
				note["type"] = noteTypes[type]
				note["pos"] = noteStruct[1]
				if type == 10 or type == 12:
					note["hits"] = noteStruct[3]
				elif not scoreInit:
					scoreInit = noteStruct[3]
					scoreDiff = noteStruct[4]
				if type == 6 or type == 9 or type == 10 or type == 12:
					note["length"] = noteStruct[5]
				bar[barIndex] = note
				if debug:
					print(" ({0})".format(nameValue(note)))
				start += 0x20 if type == 6 or type == 9 else 0x18
			bar["length"] = totalNotes
			bars.append(bar)
			
			start += 0x10
			if start >= size:
				break
	
	if len(bars) == 0:
		return
	
	osu = []
	osu.append(b"""osu file format v14

[General]""")
	if not wave:
		wave = "SONG_{0}.wav".format(filenameNoExt.split("_")[0].upper())
	osu.append(b"AudioFilename: " + bytes(wave, "utf8"))
	osu.append(b"""
AudioLeadIn: 0
PreviewTime: 0
CountDown: 0
SampleSet: Normal
StackLeniency: 0.7
Mode: 1
LetterboxInBreaks: 0
WidescreenStoryboard: 0

[Editor]
DistanceSpacing: 0.8
BeatDivisor: 4
GridSize: 4
TimelineZoom: 1

[Metadata]""")
	if not title:
		title = filenameNoExt
	osu.append(b"Title:" + bytes(title, "utf8"))
	osu.append(b"TitleUnicode:" + bytes(title, "utf8"))
	osu.append(b"""Artist:
ArtistUnicode:
Creator:
Version:
Source:
Tags:

[Difficulty]
HPDrainRate:3
CircleSize:5
OverallDifficulty:3
ApproachRate:5
SliderMultiplier:1.4
SliderTickRate:4

[TimingPoints]""")
	for i in range(len(bars)):
		prevBar = bars[i - 1] if i != 0 else None
		bar = bars[i]
		if i == 0 or prevBar["bpm"] != bar["bpm"] or prevBar["gogo"] != bar["gogo"] or prevBar["speed"] != bar["speed"]:
			offset = bar["offset"] - globalOffset
			if i == 0 or prevBar["bpm"] != bar["bpm"]:
				msPerBeat = 1000.0 / bar["bpm"] * 60.0
			elif prevBar["speed"] != bar["speed"]:
				msPerBeat = -100 / bar["speed"]
			else:
				msPerBeat = -100
			gogo = 1 if bar["gogo"] else 0
			osu.append(bytes("{0},{1},4,1,0,100,1,{2}".format(int(offset), msPerBeat, gogo), "ansi"))
	osu.append(b"")
	osu.append(b"")
	osu.append(b"[HitObjects]")
	osuSounds = {
		"Don": 0,
		"Ka": 8,
		"DON": 4,
		"KA": 12,
		"Drumroll": 0,
		"DRUMROLL": 4,
		"Balloon": 0,
		"Kusudama": 0
	}
	for bar in bars:
		for i in range(bar["length"]):
			note = bar[i]
			type = note["type"]
			offset = bar["offset"] + note["pos"] - globalOffset
			if type == "Don" or type == "Ka" or type == "DON" or type == "KA":
				sound = osuSounds[type]
				osu.append(bytes("416,176,{0},1,{1},0:0:0:0:".format(int(offset), sound), "ansi"))
			elif type == "Drumroll" or type == "DRUMROLL":
				sound = 0 if type == "Drumroll" else 4
				velocity = 1.4 * bar["speed"] / 5
				pixelLength = note["length"] * velocity
				osu.append(bytes("416,176,{0},2,{1},L|696:176,1,{2},0|0,0:0|0:0,0:0:0:0:".format(int(offset), sound, int(pixelLength)), "ansi"))
			elif type == "Balloon" or type == "Kusudama":
				sound = osuSounds[type]
				endTime = offset + note["length"]
				osu.append(bytes("416,176,{0},12,0,{1},0:0:0:0:".format(int(offset), int(endTime)), "ansi"))
	osu.append(b"")
	
	with open("{0}.osu".format(filenameNoExt), "bw+") as file:
		file.write(b"\n".join(osu))

def readByte(file, seek, length, type=None):
	file.seek(seek)
	bytes = file.read(length)
	if type == "int":
		return int.from_bytes(bytes, byteorder="big")
	elif type == "float":
		return struct.unpack(">f", bytes)[0]
	return bytes

def shortHex(number):
	return hex(number)[2:]

def nameValue(list):
	string = []
	for name in list:
		if name == "type":
			string.append(list[name])
		else:
			string.append("{0}: {1}".format(name, list[name]))
	return ", ".join(string)

if __name__=="__main__":
	if len(sys.argv) == 1:
		print(usage.format(fumen2osu_version, sys.argv[0]))
	else:
		args = sys.argv[1:]
		kwargs = {}
		flags = {
			"title": "string",
			"wave": "string",
			"debug": "bool"
		}
		argsLen = len(args)
		for i in range(argsLen):
			index = argsLen - i - 1
			arg = args[index]
			if arg[:1] == "/":
				flag = arg[1:]
				if flag in flags:
					if flags[flag] == "string" and index < argsLen - 1:
						kwargs[flag] = args.pop(index + 1)
					elif flags[flag] == "bool":
						kwargs[flag] = True
				args.pop(index)
		readFumen(*args[:2], **kwargs)
