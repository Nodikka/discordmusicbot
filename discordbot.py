import asyncio
import discord
import yt_dlp
import os

from discord.ext import commands


TOKEN = ''  #TOKEN INSERT

yt_dlp.utils.bug_reports_message = lambda: ''

ytdlp_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  
}


ffmpeg_options = {
    'options': '-vn',
}
cur_filename = []
ytdlp = yt_dlp.YoutubeDL(ytdlp_format_options)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("!"),
    description='Relatively simple music bot example',
    intents=intents,
)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdlp.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
        filename = data['url'] if stream else ytdlp.prepare_filename(data)
        global cur_filename
        cur_filename.append(filename)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
    


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = asyncio.Queue()

    async def play_music(self, ctx, player):
        loop = asyncio.get_event_loop()
        ctx.voice_client.play(player, after=lambda e: loop.create_task(self.play_next(ctx)))

    async def play_next(self, ctx):
        if not self.queue.empty():
            player = await self.queue.get()
            await self.play_music(ctx, player)
            await ctx.channel.send(f'Now playing: {player.title}')
            if len(cur_filename) > 1:
                try:
                    os.remove(cur_filename[0])
                    cur_filename.pop(0)
                except:
                    print(cur_filename[0])
        else:
            await ctx.channel.send("Queue ended!")
            for x in cur_filename:
                try:
                    os.remove(x)
                except:
                    print(x)

    @commands.command()
    async def join(self, ctx):
        """Joins a voice channel"""
        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()

    @commands.command()
    async def play(self, ctx, *, query):
        """Plays a file from the local filesystem"""

        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(query))
        ctx.voice_client.play(source, after=lambda e: print(f'Player error: {e}') if e else None)

        await ctx.send(f'Now playing: {query}')

    @commands.hybrid_command(name="music", with_app_command=True)
    async def yt(self, ctx, *, url):
        player = await YTDLSource.from_url(url, loop=self.bot.loop)
        await self.queue.put(player)
        if not ctx.voice_client.is_playing():
            await self.play_next(ctx)
        await ctx.send(f'Added to queue: {player.title}')

    @commands.hybrid_command(name="stream", with_app_command=True)
    async def stream(self, ctx, *, url):
        """Streams from a url (same as yt, but doesn't predownload)"""

        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

        await ctx.send(f'Now playing: {player.title}')

    @commands.hybrid_command(name="next", with_app_command=True)
    async def next(self, ctx,):
        ctx.voice_client.stop()
    
    @commands.command()
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Changed volume to {volume}%")

    @commands.hybrid_command(name="stop", with_app_command=True)
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        await ctx.voice_client.disconnect()
        await ctx.send(f"Music stopped!")
        for x in cur_filename:
                try:
                    os.remove(x)
                except:
                    await self.queue.task_done()
                    print(x)
        for x in cur_filename:
                try:
                    os.remove(x)
                except:
                    await self.queue.task_done()
                    print(x)
    
    @play.before_invoke
    @yt.before_invoke
    @stream.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')



async def main():
    async with bot:
        await bot.add_cog(Music(bot))
        await bot.start(TOKEN)


asyncio.run(main())