import discord, re
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

class DSSClient(discord.Client):
	voice_client = None

	async def on_ready(self):
		print("Logged in as %s" % self.user)

	async def on_message(self, message):
		if message.content[0] == "!":
			content = message.content[1:]
			res = re.search(r"([a-z]+)\s*([A-Za-z0-9]*)", content)
			if res:
				command = res.group(1)
				arg = res.group(2)

				if command == "join":
					await message.channel.send("Joining %s" % arg)
					for channel in await message.guild.fetch_channels():
						if channel.name == arg:
							self.voice_client = await channel.connect()
							print(self.voice_client)
				elif command == "debug":
					await message.channel.send("Gotcha")
					print(message)
				elif command == "disconnect":
					await message.channel.send("Disconnecting")
					await self.voice_client.disconnect()

def main():
	print("Logging in...")
	DSSClient().run(auth_keys["bot_token"])

if __name__ == "__main__":
	main()
