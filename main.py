import discord, subprocess, re, pafy
from youtubesearchpython import VideosSearch
from time import sleep

#In the same directory as this main.py, keys.py shall contain a structure like this
#auth_keys = {
#	"bot_token" : "tokengoeshere",
#	"bot_author_id" : "your_discord_user_id"
#}
from keys import auth_keys

#URL to add bot:
#https://discord.com/oauth2/authorize?client_id=916447481208918026&scope=bot&permissions=283471010816

def list_fields(ob):
	for i in dir(ob):
		print(i)

def format_dict(d, indent=0):
	s = "\t" * indent + "{\n"
	for key, value in d.items():
		if type(value) == type({}):
			s += (indent + 1) * "\t" + "%s :\n%s" % (key, format_dict(value, indent+1))
		else:
			s += (indent + 1) * "\t" + "%s : %s\n" % (key, value)
	s += "\t" * indent + "}\n"
	return s

def format_dicts(ds):
	ress = "[\n"
	for d in ds:
		ress += format_dict(d, indent=1) + "\n"
	ress += "]"		
	return ress

def print_dict(d, indent=0):
	print(format_dict(d, indent))

def print_dicts(ds):
	for d in ds:
		print_dict(d)

def voice_info_from_author(author_voice_infos, author):
	voice_info = None
	if author.voice == None:
		return None

	for info in author_voice_infos:
		if author.voice.channel.id == info.voice_client.channel.id:
			voice_info = info
			break
	return voice_info

class VoiceChannelInfo:
	def __init__(self, voice_client):
		self.voice_client = voice_client
		self.song_queue = []
		self.stream_process = None

play_keywords = ["p", "play"]
lyrics_keywords = ["l", "lyrics"]
disconnect_keywords = ["d", "disc", "disconnect"]
help_keywords = ["?", "h", "help"]

#This is the main class that subclasses Client
#Each overridden method represents a Discord event we want to respond to
class DSSClient(discord.Client):
	#Called when the client is done preparing the data received from Discord.
	#Usually after login is successful and the Client.guilds and co. are filled up.
	async def on_ready(self):
		self.voice_channel_infos = []

		print("Logged in as %s" % self.user)

	#Called when someone begins typing a message.
	async def on_typing(self, channel, user, when):
		print("%s started typing in \"%s/%s\" at %s" % (user.name, channel.guild.name, channel.name, when))

	#Called when a message is sent in a guild the bot is a member of
	async def on_message(self, message):
		#Check for blank message
		if message.content == "":
			return

		prelude = "!dss" #Beginning part of message that allows us to know it's a command for us to interpret

		#Most messages will make this statement false
		if message.content[0:len(prelude)] == prelude:
			author = message.author
			channel = message.channel

			print("%s said:\n\t\"%s\"" % (author.name, message.content))

			#Check if we already have a voice client in the author's channel
			#voice_client becomes None if we don't
			author_voice_info = voice_info_from_author(self.voice_channel_infos, author)

			content = message.content[len(prelude):]
			res = re.match(r"\s+([^\s]+)\s*(.*)", content)

			#Passes if the user's message is a syntactically correct command
			if res:
				command = res.group(1)
				args = res.group(2).split(" ")

				if command in play_keywords:
					if author.voice == None:
						await channel.send("<@%s> You must be in a voice channel to summon me." % author.id)
						return

					if author_voice_info == None:
						for guild_channel in await message.guild.fetch_channels():
							if guild_channel.id == author.voice.channel.id:
								await channel.send("Joining voice channel \"%s\"..." % guild_channel.name)
								author_voice_info = VoiceChannelInfo(await guild_channel.connect())
								await message.guild.change_voice_state(channel=author_voice_info.voice_client.channel, self_mute=False, self_deaf=True)
								self.voice_channel_infos.append(author_voice_info)
								break
					else:
						client = author_voice_info.voice_client
						#if client.is_playing():

						author_voice_info.voice_client.stop()

					#Play something
					thing_to_play = res.group(2)
					if re.search(r"^http[s]?://", thing_to_play):
						stream_url = pafy.new(thing_to_play).getbestaudio().url
						await channel.send("Now playing %s..." % thing_to_play)
						audio_source = discord.FFmpegPCMAudio(stream_url)
						author_voice_info.voice_client.play(audio_source)
					else:
						await channel.send("Searching for \"%s\"..." % thing_to_play)
						search = VideosSearch(thing_to_play, limit=1)
						search_result = search.result()["result"][0]

						stream_url = pafy.new(search_result["link"]).getbestaudio().url
						await channel.send("Now playing %s..." % search_result["link"])
						audio_source = discord.FFmpegPCMAudio(stream_url)
						author_voice_info.voice_client.play(audio_source)

					

				elif command == "debug":
					await message.channel.send("Gotcha")
					print(str(message))

				elif command in disconnect_keywords:
					if author.voice == None:
						await channel.send("<@%s> You may not disconnect me when we're not even in the same room!" % author.id)
						return

					if author_voice_info == None:
						await channel.send("I'm not currently connected to a voice channel.")
					else:
						await channel.send("Disconnecting...")
						author_voice_info.voice_client.stop()
						await author_voice_info.voice_client.disconnect()

						self.voice_channel_infos.remove(author_voice_info)

				elif command in help_keywords:
					dash_count = 30
					man_message = "%s**D**riscoll's **S**ound **S**treamer%s\n\n" % ('-'*dash_count, '-'*dash_count)
					man_message += "I am a music streaming bot that can stream music from YouTube given a direct URL or search query.\n\n"
					man_message += "\tTo summon me to your channel to play something:\n\t\t\"!dss play|p <url or query>\"\n"
					man_message += "\tTo banish me from the channel you're in:\n\t\t\"!dss d|disc|disconnect\"\n"
					man_message += "\tTo display this very help message:\n\t\t\"!dss ?|h|help\"\n"
					man_message += "\n\tContact <@%s> to report any issues or bugs." % auth_keys["bot_author_id"]
					await channel.send(man_message)

				else:
					await channel.send("Unrecognized command: %s" % command)

#Entry point
def main():
	print("Logging in...")
	DSSClient().run(auth_keys["bot_token"])

if __name__ == "__main__":
	main()
