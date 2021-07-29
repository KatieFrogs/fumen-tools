#!/usr/bin/env python3

import os

lyrics2vtt_version = "v1.1"

def readDrp(inputFile):
	import drpextract
	import xml.etree.ElementTree as ET
	
	for outFile in drpextract.extractFile(inputFile):
		xmlContent = outFile["data"]
		break
	tree = ET.ElementTree(ET.fromstring(xmlContent))
	
	lyrics = []
	root = tree.getroot()
	if root.tag == "DB_DATA":
		for dataset in root:
			if dataset.tag == "DATA_SET":
				time = None
				text = None
				for data in dataset:
					if data.tag == "words":
						if data.text == None:
							text = b""
						else:
							text = data.text.encode("utf-8", "ignore")
					elif data.tag == "wordsTime":
						try:
							time = float(data.text)
						except ValueError:
							pass
				if time != None and text != None:
					lyrics.append({
						"time": time,
						"text": text
					})
	return lyrics

def readBin(inputFile):
	import struct
	
	if type(inputFile) is str:
		file = open(inputFile, "rb")
	else:
		file = inputFile
	size = os.fstat(file.fileno()).st_size
	
	order = ""
	
	def readStruct(format, seek=None):
		if seek != None:
			file.seek(seek)
		return struct.unpack(order + format, file.read(struct.calcsize(order + format)))
	
	blank = readStruct(">III", 0x4)
	if sum(blank) != 0:
		import lzss3
		
		file.seek(0x0)
		contents = lzss3.decompress_file(file)
		file.close()
		file = FileObj(contents)
		size = len(file.array)
	
	lengthBig = readStruct(">I", 0x0)[0]
	lengthLittle = readStruct("<I", 0x0)[0]
	if lengthBig < lengthLittle:
		order = ">"
		length = lengthBig
	else:
		order = "<"
		length = lengthLittle
	
	file.seek(0xc, os.SEEK_CUR)
	
	lyrics = []
	for lineNumber in range(length):
		time = readStruct("f")[0]
		file.seek(0xc, os.SEEK_CUR)
		text = file.read(0x80)
		index = text.find(0x0)
		if index != -1:
			text = text[:index]
		text = text.decode("shift-jis", "ignore").encode("utf-8", "ignore")
		lyrics.append({
			"time": time,
			"text": text
		})
		if file.tell() >= size:
			break
	
	file.close()
	return lyrics

def writeVtt(lyrics, outputFile=None, inputFile=None):
	import io
	
	if not lyrics or len(lyrics) == 0:
		return False
	
	if inputFile:
		if type(inputFile) is str:
			filename = inputFile
		else:
			filename = inputFile.name
		filenameNoExt = os.path.splitext(filename)[0]
		outputFile = outputFile or "{0}.vtt".format(filenameNoExt)
	
	vtt = []
	vtt.append(b"WEBVTT Offset: 0")
	vtt.append(b"")
	length = len(lyrics)
	for i in range(length):
		if not lyrics[i]["text"]:
			continue
		start = lyrics[i]["time"]
		if i != length - 1:
			end = lyrics[i + 1]["time"]
		elif i != 0:
			end = start * 2 - lyrics[i - 1]["time"]
		else:
			end = start + 5
		vtt.append(timeSeconds(start) + b" --> " + timeSeconds(end))
		vtt.append(lyrics[i]["text"])
		vtt.append(b"")
	vttContents = b"\n".join(vtt)
	
	if outputFile:
		if type(outputFile) is str:
			file = open(outputFile, "bw+")
		else:
			file = outputFile
		if type(outputFile) is io.TextIOWrapper:
			sys.stdout.buffer.write(vttContents)
		else:
			file.write(vttContents)
			file.close()
		return True
	else:
		return vttContents

def timeSeconds(seconds):
	m, s = divmod(seconds, 60)
	h, m = divmod(m, 60)
	if h == 0:
		time = "{:02.0f}:{:06.3f}".format(m, s)
	else:
		time = "{:02.0f}:{:02.0f}:{:06.3f}".format(h, m, s)
	return time.encode()

class FileObj:
	def __init__(self, array):
		self.array = array
		self.pos = 0
	def seek(self, target, whence = 0):
		if whence == os.SEEK_CUR:
			self.pos += target
		elif whence == os.SEEK_END:
			self.pos = len(self.array) - target
		else:
			self.pos = target
	def read(self, size = -1):
		pos = self.pos
		if size == -1:
			self.pos = len(self.array)
			return self.array[pos:]
		else:
			self.pos = pos + size
			return self.array[pos:pos + size]
	def tell(self):
		return self.pos
	def close(self):
		del self.array

if __name__=="__main__":
	import argparse, sys
	
	parser = argparse.ArgumentParser(
		description="lyrics2vtt {0}".format(lyrics2vtt_version)
	)
	parser.add_argument(
		"file.drp",
		help="Path to a Taiko no Tatsujin lyrics file, which can be .drp, .bin, or .cbin",
		type=argparse.FileType("rb")
	)
	parser.add_argument(
		"-o",
		metavar="file.vtt",
		help="Set the filename of the output subtitle file.",
		type=argparse.FileType("bw+")
	)
	if len(sys.argv) == 1:
		parser.print_help()
	else:
		args = parser.parse_args()
		inputFile = getattr(args, "file.drp")
		filename = inputFile.name
		fileExt = os.path.splitext(filename)[1]
		if fileExt == ".drp":
			lyrics = readDrp(inputFile)
		else:
			lyrics = readBin(inputFile)
		writeVtt(lyrics, args.o, inputFile)
