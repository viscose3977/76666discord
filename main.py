import discord
from discord.ext import commands
import aiohttp
import re
import asyncio
import os


# 驗證超時時間（秒）
VERIFICATION_TIMEOUT = 300  # 5 分鐘

# 建立 intents
intents = discord.Intents.default()
intents.members = True            # 接收成員加入事件
intents.message_content = True    # 訊息內容讀取權限

bot = commands.Bot(command_prefix="!", intents=intents)

# 用來儲存每個用戶的驗證頻道 id
verification_channels = {}
# 用來儲存每個用戶點擊按鈕後預期驗證的平台
expected_platforms = {}

# 定義驗證超時檢查函式
async def check_verification_timeout(member_id, guild, channel_id, timeout=VERIFICATION_TIMEOUT):
    await asyncio.sleep(timeout)
    if member_id in verification_channels:
        member = guild.get_member(member_id)
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send("認證時間已過，您未完成認證，將被移除。")
            try:
                await channel.delete(reason="未完成認證，自動刪除驗證頻道")
            except Exception as e:
                print(f"刪除驗證頻道失敗: {e}")
        if member:
            try:
                await guild.kick(member, reason="未完成認證")
            except Exception as e:
                print(f"踢出成員失敗: {e}")
        # 清除記錄
        verification_channels.pop(member_id, None)
        expected_platforms.pop(member_id, None)

# 建立驗證按鈕的 UI
class VerificationView(discord.ui.View):
    def __init__(self, member: discord.Member):
        super().__init__()
        self.member = member

    @discord.ui.button(label="Threads 帳號", style=discord.ButtonStyle.primary)
    async def threads_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.member:
            await interaction.response.send_message("這個按鈕不是給你的！", ephemeral=True)
            return
        # 設定預期的平台為 threads
        expected_platforms[interaction.user.id] = "threads"
        await interaction.response.send_message(
            "請直接貼上您的 Threads 帳號網址於此頻道進行驗證。\n"
            "如 https://www.threads.net/@ikkirarara3089\n"
            "請勿使用範例網址進行驗證，因為76會直接停權你。\n"
            "若貼上正確網址，卻顯示錯誤訊息\n"
            "# 請嘗試反覆傳送。",
            ephemeral=True
        )

    @discord.ui.button(label="Instagram 帳號", style=discord.ButtonStyle.primary)
    async def instagram_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.member:
            await interaction.response.send_message("這個按鈕不是給你的！", ephemeral=True)
            return
        # 設定預期的平台為 instagram
        expected_platforms[interaction.user.id] = "instagram"
        await interaction.response.send_message(
            "請直接貼上您的 Instagram 帳號網址於此頻道進行驗證。\n"
            "如 https://www.instagram.com/ikkirarara3089\n"
            "請勿使用範例網址進行驗證，因為76會直接停權你。\n"
            "若貼上正確網址，卻顯示錯誤訊息\n"
            "# 請嘗試反覆傳送。",
            ephemeral=True
        )

    @discord.ui.button(label="YouTube 帳號", style=discord.ButtonStyle.primary)
    async def youtube_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.member:
            await interaction.response.send_message("這個按鈕不是給你的！", ephemeral=True)
            return
        # 設定預期的平台為 youtube
        expected_platforms[interaction.user.id] = "youtube"
        await interaction.response.send_message(
            "請直接貼上您的 YouTube 帳號網址於此頻道進行驗證。\n"
            "如 https://www.youtube.com/@Ikkira一綺羅\n"
            "請勿使用範例網址進行驗證，因為76會直接停權你。\n"
            "若貼上正確網址，卻顯示錯誤訊息\n"
            "# 請嘗試反覆傳送。",
            ephemeral=True
        )

# 當新成員加入時，在【驗證區】類別下建立驗證頻道
@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild

    # 嘗試取得名稱為「【驗證區】」的類別，名稱必須完全吻合
    category = discord.utils.get(guild.categories, name="【海關】")
    if category is None:
        # 若不存在，則自動建立一個
        category = await guild.create_category("【海關】")

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        member: discord.PermissionOverwrite(read_messages=True)
    }
    channel_name = f"驗證-{member.display_name}"
    verification_channel = await guild.create_text_channel(channel_name, overwrites=overwrites, category=category)
    # 儲存該用戶的驗證頻道 id
    verification_channels[member.id] = verification_channel.id
    await verification_channel.send("歡迎降落，請在五分鐘內完成身分驗證！ \n"
    "有任何狀況或疑問請私訊管理員！")
    await verification_channel.send("請選擇您想使用的驗證方式：", view=VerificationView(member))
    # 啟動超時檢查任務
    bot.loop.create_task(check_verification_timeout(member.id, guild, verification_channel.id))

# 當使用者在驗證頻道貼上訊息時，自動檢查是否為 URL 並進行驗證
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # 檢查訊息是否來自該使用者的驗證頻道
    if message.author.id in verification_channels and message.channel.id == verification_channels[message.author.id]:
        content = message.content.strip()
        # 判斷是否為 URL
        if re.match(r'https?://\S+', content):
            # 檢查使用者是否已選擇驗證平台
            expected = expected_platforms.get(message.author.id)
            if not expected:
                await message.channel.send("請先點選按鈕選擇驗證方式，再貼上您的個人網址。")
                return

            # 定義各平台的範例 URL，若直接貼上範例則視為濫用，直接停權（封禁）
            sample_urls = {
                "youtube": "https://www.youtube.com/@Ikkira一綺羅",
                "instagram": "https://www.instagram.com/ikkirarara3089/",
                "threads": "https://www.threads.net/@ikkirarara3089"
            }
            if expected in sample_urls and content == sample_urls[expected]:
                await message.channel.send("請勿使用範例網址進行驗證 \n # 停權！")
                try:
                    await message.guild.ban(message.author, reason="使用範例網址進行驗證")
                except Exception as e:
                    await message.channel.send(f"停權用戶時發生錯誤：{e}")
                return

            # 檢查 URL 是否包含對應網域
            if expected == "youtube" and "youtube.com" not in content:
                await message.channel.send("你選擇的是 YouTube 驗證，但貼上的網址不是 YouTube 喔。")
                return
            if expected == "instagram" and "instagram.com" not in content:
                await message.channel.send("你選擇的是 Instagram 驗證，但貼上的網址不是 Instagram 喔。")
                return
            if expected == "threads" and "threads.net" not in content:
                await message.channel.send("你選擇的是 Threads 驗證，但貼上的網址不是 Threads 喔。")
                return

            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(content) as response:
                        if response.status == 200:
                            # 驗證成功後指派身分組「喔沒有我只是看看」
                            role = discord.utils.get(message.guild.roles, name="喔沒有我只是看看")
                            if role:
                                await message.author.add_roles(role)
                            await message.channel.send("驗證成功，歡迎加入！")
                            # 驗證完成後自動刪除驗證頻道
                            await message.channel.delete(reason="驗證完成，自動刪除驗證頻道")
                            # 清除該使用者的記錄
                            verification_channels.pop(message.author.id, None)
                            expected_platforms.pop(message.author.id, None)
                        else:
                            await message.channel.send(f"驗證失敗：收到狀態碼 {response.status}。請確認 URL 是否正確。")
                except Exception as e:
                    await message.channel.send(f"驗證失敗：發生錯誤 ({e})，請稍後再試。")
    await bot.process_commands(message)

@bot.event
async def on_member_remove(member: discord.Member):
    # 如果該用戶有驗證頻道存在，則取得頻道並刪除
        if member.id in verification_channels:
            channel_id = verification_channels[member.id]
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.delete(reason="用戶已離開伺服器，刪除驗證頻道")
            # 清除該用戶的驗證頻道與預期平台記錄
            verification_channels.pop(member.id, None)
            expected_platforms.pop(member.id, None)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")


bot.run(os.environ["TOKEN"])
