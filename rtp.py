#!/usr/bin/env python

from threading import Thread, Lock
import inotify.adapters
import select
import fcntl
import os
import io
import sys
import wave
import audioop
import time
from google.cloud import speech
from pprint import pprint

mutex = Lock()

calls = {}
read_list = []
wav_files = {}

clients = {}
streams = {}
samples = {}

trans = {}

def _open_stream(idx):

	ctx = calls[idx]
	pprint(ctx)
	j = 0
	if 'OPEN_STREAMS' not in ctx:
		ctx['OPEN_STREAMS'] = []
	while True:
		key = "STREAM " + str(j) + " interface"
		if key in ctx:
			if "RTP" in ctx[key]:
				if j in ctx['OPEN_STREAMS']:
					print "interface " + str(j) + " already open"
				else:
					print "interface " + str(j) + " not open yet, opening " + ctx[key] + " ..."
					path = "/proc/rtpengine/0/calls/" + idx + "/" + ctx[key]
					
					file = open(path, "rb")
					fd = file.fileno()
					flag = fcntl.fcntl(fd, fcntl.F_GETFL)
					fcntl.fcntl(fd, fcntl.F_SETFL, flag | os.O_NONBLOCK)
					mutex.acquire()
					read_list.append(file)
					mutex.release()
					ctx['OPEN_STREAMS'].append(j)
					
			else:
				print "skip non-RTP interface " + ctx[key]
			j = j+1
		else:
			break
	calls[idx] = ctx

def _watch_spool():
	i = inotify.adapters.InotifyTree(b'/var/spool/rtpengine')
	print "waiting for new calls"
	for event in i.event_gen():
		if(event == None):
			continue
		(header, type_names, watch_path, filename) = event
		if 'IN_CLOSE_WRITE' in type_names:
			idx = _read_meta(watch_path + "/" + filename)
			_open_stream(idx)
		if 'IN_DELETE' in type_names:
			_cleanup(filename)
	

def _cleanup(name):
	if name.endswith('.meta'):
		name = name[:-5]
		print "cleaning up " + name
		if name in calls:
			del calls[name]

		# TODO: stop threads, remove tmp files

def _read_meta(path):
	print "reading " + path
	file = open(path, "r")
	idx = None
	dlen = None
	data = ''
	ctx = {}
	for line in file:
		if idx == None:
			if len(line) <= 1:
				continue
			idx = line.rstrip('\n')
			# print "  got idx " + idx
		elif dlen == None:
			dlen = int(line.rstrip('\n').rstrip(':'))
			# print "  got dlen " + str(dlen)
		else:
			# print "  got data line " + data.rstrip('\n')
			data = data + line
			# print "  read " + str(len(data)) + "/"  + str(dlen) + " chars"
			if len(data) >= dlen:
				# print "  -- closing idx " + idx
				diff = (len(data) - dlen) * -1
				if diff < 0:
					ctx[idx] = data[:diff]
				else:
					ctx[idx] = data
				idx = None
				dlen = None
				data = ''
	pprint(ctx)
	print "done reading file\n"
	idx = ctx['PARENT']
	if idx in calls:
		oldctx = calls[idx]
		oldctx.update(ctx)
		calls[idx] = oldctx
		print "updated existing call " + idx
	else:
		print "added new call " + idx
		calls[idx] = ctx
	return idx

def _recognize(path, idx):
	client = speech.Client()

	stream = open(path, "rb")
	sample = client.sample(
		stream = stream,
		encoding = speech.encoding.Encoding.LINEAR16,
		sample_rate_hertz = 8000
	)

	while True:
		time.sleep(0.5)

		print "send data to google"

		try:
			results = sample.streaming_recognize(
				language_code = 'en-US',
				speech_contexts = ['mailbox', 'folder', 'change', 'pound', 'star', 'options', 'folder']
			)

			for result in results:
				for alternative in result.alternatives:
					print('-' * 20)
					print('transcript: ' + alternative.transcript)
					print('confidence: ' + str(alternative.confidence))

					if idx not in trans:
						trans[idx] = ''
					trans[idx] += alternative.transcript + " "
					print ">>> " + str(idx) + ": " + trans[idx]
		except:
			pass

def _read_stream(stream):

	try:
		data = stream.read(65535)
		data = bytearray(data)
		
		# skip ip header (4x val of ihl field in ip hdr, plus 8 byte udp hdr)
		ihl = int(data[0]) & 0x0f;
		data = data[(4*ihl) + 8:]

		v = data[0] >> 6

		if v == 2:
			cc = (data[0]) & 0x0f
			pt = data[1] & 0x7f
			print "v=" + str(v) + ", pt=" + str(pt)
			data = data[12:] # skip over fixed hdr len
			if cc > 0:
				data = data[cc*4:]
				# TODO: what about profile specific extensions?

			idx = stream.fileno()
			file_name = "/tmp/out-" + str(idx) + ".wav"
			if idx not in wav_files:
				wav = wave.open(file_name, "wb")
				wav.setparams((1, 2, 8000, 0, 'NONE', 'NONE'))
				wav_files[idx] = wav

				t = Thread(target=_recognize, args=(file_name, idx))
				t.daemon = True
				t.start()


			wav = wav_files[idx]

			strdata = "".join(map(chr, data))
			pcm = audioop.alaw2lin(strdata, 2)
			wav.writeframes(pcm)


		# else:
			# not an rtp packet

		
	except IOError:
		pass

def _main():

	t = Thread(target=_watch_spool, args = ())
	t.daemon = True
	t.start()

	while True:
		print "waiting for data in files"
		mutex.acquire()
		rlist = read_list
		mutex.release()

		ready, _, _ = select.select(rlist, [], [], 1)

		#print str(len(ready)) + " files ready for reading"
		for stream in ready:
			#print "fileno " + str(stream.fileno()) + " ready for reading"
			_read_stream(stream)

if __name__ == '__main__':
	_main()
