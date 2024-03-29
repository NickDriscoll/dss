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

#The valid keywords to trigger each command
play_keywords = ["p", "play"]
pause_keywords = ["pause", "unpause"]
skip_keywords = ["n", "next", "s", "skip"]
lyrics_keywords = ["l", "lyrics"]
disconnect_keywords = ["d", "disc", "disconnect", "stop"]
help_keywords = ["?", "h", "help"]

#Examples of how to use commands
play_example = "\"!dss p katamari mamba\", \"!dss play https://www.youtube.com/watch?v=OOhW_Qc5oiU\""
pause_example = "\"!dss pause\", \"!dss unpause\""
skip_example = ""

def format_keywords(keywords):
	res = ""
	first = True
	for word in keywords:
		if first:
			first = False
			res = word
		else:
			res += "|%s" % word
	return res

#Define the manual message
dash_count = 30
man_message = "%s**D**riscoll's **S**ound **S**treamer%s\n\n" % ('-'*dash_count, '-'*dash_count)
man_message += "I am a music bot that can stream sound from a YouTube video given a direct URL or search query.\n"
man_message += "\n\tTo summon me to play/queue something:\n\t\t\"!dss %s <url or query>\"" % format_keywords(play_keywords)
man_message += "\n\tTo skip to the next queued track:\n\t\t\"!dss %s\"" % format_keywords(skip_keywords)
man_message += "\n\tTo toggle music playback (pausing):\n\t\t\"!dss %s\"" % format_keywords(pause_keywords)
man_message += "\n\tTo expel me from the channel you're in:\n\t\t\"!dss %s\"" % format_keywords(disconnect_keywords)
man_message += "\n\tTo display this help message:\n\t\t\"!dss %s\"" % format_keywords(help_keywords)
man_message += "\n\tContact <@%s> to report any issues or bugs." % auth_keys["bot_author_id"]

#Regex used to determine if a string is a URL
URL_REGEX = r"^http[s]?://"

def flushed_print(message):
	print(message, flush=True)

#Returns the first url given the search query
def url_from_query(query):
	search = VideosSearch(query, limit=1)
	search_results = search.result()["result"]
	if len(search_results) == 0:
		return None
	else:
		return search_results[0]["link"]

async def send_and_print(channel, message):
	flushed_print(message)
	await channel.send(message)

#An instance of this class holds all the data for an active voice connection
class VoiceConnectionInfo:
	def __init__(self, message_channel, voice_client):
		self.voice_client = voice_client		#Voice client to stream to
		self.message_channel = message_channel	#The original text channel the bot was summoned with
		self.song_queue = deque()				#Queue of songs to play

#This is the main class that subclasses Client
#Each overridden method represents a Discord event we want to respond to
class DSSClient(discord.Client):
	#Custom constructor so we can avoid making the prelude a global variable
	def __init__(self, prelude):
		self.prelude = prelude				#Message start that signals it's a command for us to interpret
		self.voice_connection_infos = []	#List keeping track of data for each active voice connection
		super().__init__()					#Call the base class's constructor to make sure client init happens correctly

	#Called when the client is done preparing the data received from Discord.
	#Usually after login is successful and the Client.guilds and co. are filled up.
	async def on_ready(self):
		flushed_print("Logged in as %s" % self.user)

	#Called when someone begins typing a message
	async def on_typing(self, channel, user, when):
		flushed_print("\"%s\" started typing in \"%s/%s\" at %s" % (user.name, channel.guild.name, channel.name, when.now()))

	#Called when a message is sent in a guild (server) of which the bot is a member
	async def on_message(self, message):
		author = message.author
		channel = message.channel

		if self.user.id != author.id:
			flushed_print("\"%s\" said \"%s\"" % (author.name, message.content))

		#Early exit if the first few characters of the message don't match the bot's prelude
		#Most messages will trigger this
		if message.content[0:len(self.prelude)].lower() != self.prelude:
			return

		#This regex defines the syntax of a legal bot command
		#in English: 
		#"one or more spaces followed by
		# a group defined by any number of non-space characters followed by
		# zero or more spaces followed by a group defined by any number of any characters"
		syntax_regex = r"\s+([^\s]+)\s*(.*)"

		#Early exit if the message is not a valid command
		res = re.match(syntax_regex, message.content[len(self.prelude):])
		if not res:
			flushed_print("didn't match syntax")
			return

		#Check if we already have a voice client in the author's channel
		voice_info = None
		if author.voice != None:
			for info in self.voice_connection_infos:
				if author.voice.channel.id == info.voice_client.channel.id:
					voice_info = info
					break

		#The first group of the regex captures the command
		command = res.group(1).lower()	#Convert to lowercase to make command input case-insensitive

		#Play command
		if command in play_keywords:
			#Early exit if the message author isn't in a voice channel
			if author.voice == None:
				await send_and_print(channel, "<@%s> You must be in a voice channel to summon me." % author.id)
				return

			#If we're not in the message author's voice channel, join it
			if voice_info == None:
				for guild_channel in message.guild.channels:
					if guild_channel.id == author.voice.channel.id:
						await send_and_print(channel, "Joining voice channel \"%s\"..." % guild_channel.name)

						#Initialize voice connection info
						voice_info = VoiceConnectionInfo(channel, await guild_channel.connect())
						self.voice_connection_infos.append(voice_info)

						#Deafen ourself
						await message.guild.change_voice_state(channel=voice_info.voice_client.channel, self_mute=False, self_deaf=True)
						break

			#Everything after the command is interpreted as the url/query
			thing_to_play = res.group(2)
			if len(thing_to_play) == 0:
				await voice_info.message_channel.send("<@%s> You need to pass a url or search query to the play command." % author.id)
				return

			if not voice_info.voice_client.is_playing() and len(voice_info.song_queue) == 0:
				voice_info.song_queue.append(thing_to_play)
				await self.advance_song_queue(voice_info)
			else:
				if re.search(URL_REGEX, thing_to_play):
					voice_info.song_queue.append(thing_to_play)
					await send_and_print(voice_info.message_channel, "Queued: %s" % thing_to_play)
				else:
					await voice_info.message_channel.send("Searching for \"%s\"..." % thing_to_play)
					link = url_from_query(thing_to_play)
					voice_info.song_queue.append(link)
					await send_and_print(voice_info.message_channel, "Queued: %s" % link)

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
				await channel.send("<@%s> I'm not even connected to your voice channel." % author.id)
			else:
				await send_and_print(channel, "Disconnecting...")
				voice_info.voice_client.stop()
				await voice_info.voice_client.disconnect()
				self.voice_connection_infos.remove(voice_info)

		#Help command
		elif command in help_keywords:
			await channel.send(man_message)
			flushed_print("Displayed help manual.")
			
		else:
			await channel.send("Unrecognized command \"%s\"\nuse \"!dss %s\" to display the manual" % (command, format_keywords(help_keywords)))

	#Called when a message is edited
	async def on_message_edit(self, before, after):
		if before.content != after.content:
			await self.on_message(after)

	#Begin playing the audio from the video at link through voice_client
	def play_audio_url(self, voice_client, link):
		stream_url = pafy.new(link).getbestaudio().url
		audio_source = discord.FFmpegPCMAudio(stream_url)
		voice_client.play(audio_source, after=self.after_audio)

	#Callback that is called when an AudioSource is exhausted or has an error
	def after_audio(self, error):
		if error != None:
			flushed_print("after_audio error: %s" % error)

		#Go through all open voice connections and advance the
		#queue on the ones that need advancing
		for info in self.voice_connection_infos:
			if not info.voice_client.is_playing():
				asyncio.ensure_future(self.advance_song_queue(info), loop=self.loop)

	#Advances to the next song in voice_info's queue
	async def advance_song_queue(self, voice_info):
		if len(voice_info.song_queue) > 0:
			thing_to_play = voice_info.song_queue.popleft() #Dequeue
			if re.search(URL_REGEX, thing_to_play):
				self.play_audio_url(voice_info.voice_client, thing_to_play)
				await send_and_print(voice_info.message_channel, "Now playing: %s" % thing_to_play)
			else:
				await send_and_print(voice_info.message_channel, "Searching for \"%s\"..." % thing_to_play)
				link = url_from_query(thing_to_play)
				if link == None:
					await send_and_print(voice_info.message_channel, "Found no video results for that query. Sorry.")
				else:
					self.play_audio_url(voice_info.voice_client, link)
					await send_and_print(voice_info.message_channel, "Now playing: %s" % link)

#Entry point
def main():
	#Getting environment arg
	if len(sys.argv) < 2:
		flushed_print("Usage: \"python3 main.py <dev or prod>\"")
		return
	env = sys.argv[1]

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
		flushed_print("The argument must be one of \"dev\" or \"prod\"")
		return

	#This dicord.Client derived object creates and maintains an asyncio loop
	#which asynchronously dispatches the overridden methods when the relevant events occur
	flushed_print("Logging in...")
	DSSClient(prelude).run(bot_key)

#Standard entry point guard
if __name__ == "__main__":
	main()
