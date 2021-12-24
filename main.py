# Title: Driscoll's Sound Streamer (DSS)
# Author: Nick Driscoll

import asyncio, discord, pafy, re, sys
from collections import deque
from youtubesearchpython import VideosSearch

#In the same directory as this main.py, keys.py contains a structure like this
#auth_keys = {
#	"bot_token" : "tokengoeshere",
#	"bot_token_dev" : "devbottokenid",
#	"bot_author_id" : "your_discord_user_id"
#}
from keys import auth_keys

#-----Helper functions-----

#Returns a pretty-printed dictionary
def format_dict(d, indent=0):
	s = "\t" * indent + "{\n"
	for key, value in d.items():
		if type(value) == type({}):
			s += (indent + 1) * "\t" + "%s :\n%s" % (key, format_dict(value, indent+1))
		else:
			s += (indent + 1) * "\t" + "%s : %s\n" % (key, value)
	s += "\t" * indent + "}\n"
	return s

#Returns many pretty-printed dictionaries
def format_dicts(ds, indent=0):
	ress = "\t" * indent + "[\n"
	for d in ds:
		ress += format_dict(d, indent + 1) + "\n"
	ress += "\t" * indent + "]\n"		
	return ress

def print_dict(d, indent=0):
	print(format_dict(d, indent))

#--------------------------

#The valid keywords to trigger each command
play_keywords = ["p", "play"]
pause_keywords = ["pause", "unpause"]
skip_keywords = ["n", "next", "s", "skip"]
lyrics_keywords = ["l", "lyrics"]
disconnect_keywords = ["d", "disc", "disconnect"]
help_keywords = ["?", "h", "help"]

#Define the manual message
dash_count = 30
man_message = "%s**D**riscoll's **S**ound **S**treamer%s\n\n" % ('-'*dash_count, '-'*dash_count)
man_message += "I am a music bot that can stream sound from a YouTube video given a direct URL or search query.\n\n"
man_message += "\tTo summon me to play/queue something:\n\t\t\"!dss play|p <url or query>\"\n"
man_message += "\tTo skip to the next queued track:\n\t\t\"!dss n|next|s|skip\"\n"
man_message += "\tTo toggle music playback (pausing):\n\t\t\"!dss pause|unpause\"\n"
man_message += "\tTo expel me from the channel you're in:\n\t\t\"!dss d|disc|disconnect\"\n"
man_message += "\tTo display this very help message:\n\t\t\"!dss ?|h|help\"\n"
man_message += "\n\tContact <@%s> to report any issues or bugs." % auth_keys["bot_author_id"]

#Regex used to determine if a string is a URL
URL_REGEX = r"^http[s]?://"

#Returns the first url given the search query
def url_from_query(query):
	search = VideosSearch(query, limit=1)
	search_results = search.result()["result"]
	if len(search_results) == 0:
		return None
	else:
		result = search_results[0]
		return result["link"]

#An instance of this class holds all the data
#for an active voice connection
class VoiceConnectionInfo:
	def __init__(self, message_channel, voice_client):
		self.voice_client = voice_client		#Voice client to 
		self.message_channel = message_channel	#The original text channel the bot was summoned with
		self.song_deque = deque()				#Queue of songs to play

#This is the main class that subclasses Client
#Each overridden method represents a Discord event we want to respond to
class DSSClient(discord.Client):
	#Custom constructor so we can avoid making the prelude a global variable
	def __init__(self, prelude):
		self.prelude = prelude				#Message start that signals it's a command for us to interpret
		self.voice_connection_infos = []	#List keeping track of data for each active voice connection
		super().__init__()					#Call the base class's constructor to make sure init happens correctly

	#Called when the client is done preparing the data received from Discord.
	#Usually after login is successful and the Client.guilds and co. are filled up.
	async def on_ready(self):
		print("Logged in as %s" % self.user)

	#Called when someone begins typing a message
	async def on_typing(self, channel, user, when):
		print("%s started typing in \"%s/%s\" at %s" % (user.name, channel.guild.name, channel.name, when.now()))

	#Called when a message is sent in a guild of which the bot is a member
	async def on_message(self, message):
		#Most messages will trigger this early exit
		if message.content[0:len(self.prelude)].lower() != self.prelude:
			return

		author = message.author
		channel = message.channel

		print("%s said:\n\t\"%s\"" % (author.name, message.content))

		#Check if we already have a voice client in the author's channel
		#voice_client becomes None if we don't
		voice_info = None
		if author.voice != None:
			for info in self.voice_connection_infos:
				if author.voice.channel.id == info.voice_client.channel.id:
					voice_info = info
					break

		#This regex defines the syntax of a legal bot command
		#in English: 
		#"one or more spaces followed by
		# a group defined by any number of non-space characters followed by
		# zero or more spaces followed by a group defined by any number of any character"
		res = re.match(r"\s+([^\s]+)\s*(.*)", message.content[len(self.prelude):])

		#Early exit if the message is not a valid command
		if not res:
			print("didn't match syntax")
			return

		print("\tsyntax matched")
		command = res.group(1).lower()	#Convert to lowercase to make command input case-insensitive
		args = res.group(2).split(" ")	#Split on whitespace to get an array of arguments

		#Play command
		if command in play_keywords:
			#Early exit if the message author 
			if author.voice == None:
				await channel.send("<@%s> You must be in a voice channel to summon me." % author.id)
				return

			#If we're not in the message author's voice channel
			if voice_info == None:
				for guild_channel in message.guild.channels:
					if guild_channel.id == author.voice.channel.id:
						await channel.send("Joining voice channel \"%s\"..." % guild_channel.name)
						voice_info = VoiceConnectionInfo(channel, await guild_channel.connect())
						await message.guild.change_voice_state(channel=voice_info.voice_client.channel, self_mute=False, self_deaf=True)
						self.voice_connection_infos.append(voice_info)
						break

			#Everything after the command is interpreted as the url/query
			thing_to_play = res.group(2)
			if not voice_info.voice_client.is_playing() and len(voice_info.song_deque) == 0:
				voice_info.song_deque.append(thing_to_play)
				await self.advance_song_queue(voice_info)
			else:
				if re.search(URL_REGEX, thing_to_play):
					voice_info.song_deque.append(thing_to_play)
					await voice_info.message_channel.send("Queued: %s" % thing_to_play)
				else:
					await voice_info.message_channel.send("Searching for \"%s\"..." % thing_to_play)
					link = url_from_query(thing_to_play)
					voice_info.song_deque.append(link)
					await voice_info.message_channel.send("Queued: %s" % link)

		#Skip command
		elif command in skip_keywords:
			if voice_info == None:
				await channel.send("<@%s> I'm not playing anything" % author.id)
				return

			if voice_info.voice_client.is_playing():
				await channel.send("Skipping...")
				voice_info.voice_client.stop()
			else:
				await channel.send("<@%s> I'm not playing anything" % author.id)

		#Pause command
		elif command in pause_keywords:
			if voice_info == None:
				await channel.send("<@%s> I'm not playing anything" % author.id)
				return

			vc = voice_info.voice_client
			if vc.is_playing():
				await channel.send("Pausing...")
				vc.pause()
			elif vc.is_paused():
				await channel.send("Resuming...")
				vc.resume()

		#Disconnect command
		elif command in disconnect_keywords:
			if author.voice == None:
				await channel.send("<@%s> You can't disconnect me when we're not in the same room." % author.id)
				return

			if voice_info == None:
				await channel.send("<@%s> I'm not even connected to a voice channel." % author.id)
			else:
				await channel.send("Disconnecting...")
				voice_info.voice_client.stop()
				await voice_info.voice_client.disconnect()
				self.voice_connection_infos.remove(voice_info)

		#Help command
		elif command in help_keywords:
			await channel.send(man_message)
			
		else:
			await channel.send("Unrecognized command: \"%s\"\nuse \"!dss ?\" to display the manual" % command)

	#Called when a message is edited
	async def on_message_edit(self, before, after):
		print("Message edited: %s" % (before.id))

	#Begin playing the audio from the video at link through voice_client
	def play_audio_url(self, voice_client, link):
		stream_url = pafy.new(link).getbestaudio().url
		audio_source = discord.FFmpegPCMAudio(stream_url)
		voice_client.play(audio_source, after=self.after_audio)

	#Advances to the next song in voice_info's queue
	async def advance_song_queue(self, voice_info):
		if len(voice_info.song_deque) > 0:
			thing_to_play = voice_info.song_deque.popleft() #Dequeue
			if re.search(URL_REGEX, thing_to_play):
				self.play_audio_url(voice_info.voice_client, thing_to_play)
				await voice_info.message_channel.send("Now playing: %s" % thing_to_play)
			else:
				await voice_info.message_channel.send("Searching for \"%s\"..." % thing_to_play)
				link = url_from_query(thing_to_play)
				if link == None:
					await voice_info.message_channel.send("Found no video results for that query. Sorry.")
				else:
					self.play_audio_url(voice_info.voice_client, link)
					await voice_info.message_channel.send("Now playing: %s" % link)

	#Callback that is called when an AudioSource is exhausted or has an error
	def after_audio(self, error):
		if error != None:
			print("after_audio error: %s" % error)

		#Go through all open voice connections and advance the
		#queue on the ones that need advancing
		for info in self.voice_connection_infos:
			if not info.voice_client.is_playing():
				asyncio.ensure_future(self.advance_song_queue(info), loop=self.loop)

#Entry point
def main():
	#Getting environment arg
	if len(sys.argv) < 2:
		print("Usage: \"python3 main.py <dev or prod>\"")
		exit(0)
	env = sys.argv[1]

	print("Logging in...")

	#Configure environment related variables
	bot_key = ""				#Secret token that authenticates the script to the bot account
	prelude = ""				#Message start that signals it's a command for us to interpret
	if env == "prod":
		bot_key = auth_keys["bot_token"]
		prelude = "!dss"
	elif env == "dev":
		bot_key = auth_keys["bot_token_dev"]
		prelude = "!dssd"
	else:
		print("The argument must be one of \"dev\" or \"prod\"")
		exit(0)

	#This dicord.Client derived object creates and maintains an asyncio loop
	#which asynchronously dispatches the overridden methods when the relevant event occur
	DSSClient(prelude).run(bot_key)

#Standard entry point guard
if __name__ == "__main__":
	main()
