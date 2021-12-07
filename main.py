import discord, subprocess, re
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

def voice_client_by_author_channel(voice_clients, author_voice):
	voice_client = None
	for client in voice_clients:
		if author_voice.channel.id == client.channel.id:
			voice_client = client
			break
	return voice_client

class VoiceChannelInfo:
	def __init__(self, voice_client):
		self.voice_client = voice_client
		self.song_queue = []

#This is the main class that subclasses Client
#Each overridden method represents a Discord event we want to respond to
disconnect_keywords = ["disc", "disconnect"]
class DSSClient(discord.Client):
	voice_clients = []


	#Called when the client first becomes "ready"
	async def on_ready(self):
		print("Logged in as %s" % self.user)

	#Called when a message is sent in a guild the bot is a member of
	async def on_message(self, message):
		#Check for blank message
		if message.content == "":
			return

		prelude = "!dss " #Beginning part of message that allows us to know it's a command for us to interpret
		if message.content[0:len(prelude)] == prelude:
			author = message.author
			channel = message.channel

			content = message.content[len(prelude):]
			res = re.search(r"([a-z]+)\s*(.*)", content)

			if res:
				command = res.group(1)
				args = res.group(2).split(" ")
				print("\n%s issued : \"%s %s\"" % (author.name, command, args))

				futures = []
				if command == "play":
					if author.voice == None:
						await channel.send("<@%s> You must be in a voice channel to summon me." % author.id)
						return

					#Check if we already have a voice client in the author's channel
					voice_client = voice_client_by_author_channel(self.voice_clients, author.voice)

					if voice_client == None:
						await channel.send("Joining")
						for channel in await message.guild.fetch_channels():
							if channel.id == author.voice.channel.id:
								voice_client = await channel.connect()
								self.voice_clients.append(voice_client)
								break
					else:
						voice_client.stop()

					#Play something
					p = subprocess.Popen(args=["youtube-dl", "-f", "m4a", args[0], "-o", "-"], stdout=subprocess.PIPE)
					voice_client.play(discord.FFmpegPCMAudio(
						source=p.stdout,
						pipe=True
					))
				elif command == "debug":
					await message.channel.send("Gotcha")
					print(str(self))
					print(str(message))
				elif command in disconnect_keywords:
					if author.voice == None:
						await channel.send("<@%s> You may not disconnect me when we are not even in the same room!" % author.id)
						return

					#Check if we already have a voice client in the author's channel
					voice_client = voice_client_by_author_channel(self.voice_clients, author.voice)

					if voice_client == None:
						await channel.send("not connected to anything")
					else:
						await channel.send("Disconnecting")
						voice_client.stop()
						await voice_client.disconnect()
						self.voice_clients.remove(voice_client)
				else:
					await channel.send("Unrecognized command: %s" % command)

#Entry point
def main():
	print("Logging in...")
	DSSClient().run(auth_keys["bot_token"])

if __name__ == "__main__":
	main()
